from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from .core import Finding, cache_dir, normalized_repo_id, redact
from .detectors import detect_group
from .git import collect, file_map
from .index import RepositoryIndex
from .ollama import OllamaClient, OllamaError
from .report import verdict, write_reports
from .review import build_prompt, build_query, dedupe, evidence_gate, verify


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog="ai-review", description="Private local Ollama code review; never executes reviewed project code.")
    modes=p.add_mutually_exclusive_group()
    modes.add_argument("--base", metavar="REF", help="review merge-base(REF, HEAD)..working tree")
    modes.add_argument("--staged", action="store_true", help="review only the staged diff")
    modes.add_argument("--range", dest="range_spec", metavar="A..B", help="review an explicit Git range")
    p.add_argument("--output", default="ai-review-report", help="report directory (default: %(default)s)")
    p.add_argument("--fail-on", choices=["high","critical"], help="exit 2 when this severity or higher is confirmed")
    p.add_argument("--rebuild-index", action="store_true", help="recreate the repository index")
    p.add_argument("--index-only", action="store_true", help="update index without reviewing")
    p.add_argument("--verbose", action="store_true")
    return p


class Console:
    def __init__(self, verbose=False): self.verbose=verbose
    def info(self,msg): print(f"[ai-review] {msg}")
    def detail(self,msg):
        if self.verbose: print(f"[ai-review] {msg}")


def title(root: Path) -> str:
    subject=subprocess.run(["git","log","-1","--pretty=%s"],cwd=root,text=True,capture_output=True).stdout.strip()
    return subject or "Local changes"


def main(argv=None, client_factory=OllamaClient) -> int:
    args=parser().parse_args(argv); started=time.monotonic(); root=Path.cwd().resolve(); log=Console(args.verbose)
    if not (root/".git").exists(): print("ai-review: run from a Git repository root",file=sys.stderr); return 1
    try:
        client=client_factory(); log.info("checking local Ollama and required models")
        client.verify_models()
        db=cache_dir(root)/(normalized_repo_id(root)+".sqlite3")
        index=RepositoryIndex(root,db,client.embed)
        log.info(f"updating private index at {db} ({client.embedding_model})")
        stats=index.update(args.rebuild_index)
        log.info(f"index: {stats.files} files, {stats.chunks} chunks, {stats.embedded} embedded, {stats.reused} reused, {stats.deleted} stale removed, {stats.dimensions} dimensions")
        if args.index_only:
            log.info(f"index-only complete in {time.monotonic()-started:.1f}s"); return 0
        changed=collect(root,args.base,args.staged,args.range_spec)
        eligible=[f for f in changed if not f.binary and not f.generated and f.status!="D" and f.proposed]
        omitted=[f for f in changed if f not in eligible]
        log.info(f"changed files: {len(changed)}; eligible text: {len(eligible)}; omitted binary/generated/deleted: {len(omitted)}")
        for f in changed: log.detail(f"{f.status} {f.path}" + (" (not model-reviewed)" if f in omitted else ""))
        findings=[]; retrieval=[]; prompt_tokens=output_tokens=duration_ns=0; manifest=file_map(root)
        changed_tests=[f for f in eligible if "test" in f.path.lower() or "spec" in f.path.lower()]
        for group_no,start in enumerate(range(0,len(eligible),3),1):
            group=eligible[start:start+3]; paths={f.path for f in group}; log.info(f"focused group {group_no}: {', '.join(paths)}")
            query=build_query(group); qvec=client.embed([query])[0]; contexts=index.retrieve(query,qvec,paths,6)
            retrieval += [{k:c[k] for k in ("path","start_line","end_line")} for c in contexts]
            log.info("retrieved: "+(", ".join(f"{c['path']}:{c['start_line']}-{c['end_line']}" for c in contexts) or "none"))
            prompt=build_prompt(title(root),group,manifest,contexts)
            log.info(f"characters: diff={sum(len(f.patch) for f in group)} base={sum(len(f.base) for f in group)} proposed={sum(len(f.proposed) for f in group)} rag={sum(len(c['text']) for c in contexts)} prompt={len(prompt)}")
            deterministic=detect_group(group, changed_tests)
            try:
                response,usage=client.generate_json(prompt); raw=response.get("findings",[]) if isinstance(response,dict) else response
                modeled=[Finding.from_dict(x) for x in raw if isinstance(x,dict)]
            except OllamaError as exc:
                log.info(f"model group failed safely: {exc}"); modeled=[]; usage=type("U",(),{"prompt_tokens":0,"output_tokens":0,"duration_ns":0,"completion_reason":"error","total_tokens":0})()
            prompt_tokens+=usage.prompt_tokens; output_tokens+=usage.output_tokens; duration_ns+=usage.duration_ns
            log.info(f"Ollama: prompt={usage.prompt_tokens} output={usage.output_tokens} total={usage.total_tokens} duration={usage.duration_ns/1e9:.2f}s reason={usage.completion_reason}")
            log.info(f"candidates: model={len(modeled)} deterministic={len(deterministic)}")
            findings += deterministic+modeled
        before=len(findings); findings,dupes1=dedupe(findings); files={f.path:f for f in eligible}
        findings,rejected=evidence_gate(findings,files)
        for f in rejected: log.info(f"evidence rejection {f.file}: {f.rejection_reason}; evidence={redact(f.evidence,80)!r}")
        log.info(f"pre-verification: candidates={before} duplicates={dupes1} evidence_rejected={len(rejected)}")
        findings,verification_usage=verify(client,findings,files)
        prompt_tokens+=verification_usage.prompt_tokens; output_tokens+=verification_usage.output_tokens; duration_ns+=verification_usage.duration_ns
        findings,dupes2=dedupe(findings)
        rejected += [f for f in findings if f.classification=="rejected"]
        active=[f for f in findings if f.classification!="rejected"]
        counts={c:sum(f.classification==c for f in findings) for c in ("verified","needs_human_review","rejected")}
        data={"version":1,"verdict":verdict(findings),"coverage":{"reviewed":len(eligible),"eligible":len(eligible),"total_changed":len(changed),"omitted":[f.path for f in omitted],"complete":not omitted},"index":{"database":str(db),"files":stats.files,"chunks":stats.chunks,"embedding_model":client.embedding_model,"dimensions":stats.dimensions},"usage":{"prompt_tokens":prompt_tokens,"output_tokens":output_tokens,"total_tokens":prompt_tokens+output_tokens,"ollama_duration_seconds":round(duration_ns/1e9,3),"wall_duration_seconds":round(time.monotonic()-started,3)},"findings":[f.dict() for f in findings if f.classification!="rejected"],"rejected_count":len(rejected),"duplicates_removed":dupes1+dupes2,"retrieval":retrieval}
        reports=write_reports(Path(args.output),data)
        log.info(f"final: verified={counts['verified']} human-review={counts['needs_human_review']} rejected={len(rejected)} duplicates={dupes1+dupes2}; coverage={'complete' if not omitted else 'incomplete'}")
        log.info("reports: "+", ".join(str(p) for p in reports)); log.info(f"finished in {time.monotonic()-started:.1f}s")
        if args.fail_on:
            rank={"low":0,"medium":1,"high":2,"critical":3}; threshold=rank[args.fail_on]
            if any(f.classification=="verified" and rank.get(f.severity,0)>=threshold for f in findings): return 2
        return 0
    except (OllamaError,RuntimeError,ValueError,OSError) as exc:
        print(f"ai-review: {redact(str(exc))}",file=sys.stderr); return 1
