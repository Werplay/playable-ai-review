import unittest
from tools.ai_review.ollama import OllamaClient, OllamaError

class Stub(OllamaClient):
    def __init__(self,responses):
        super().__init__(base_url="http://local",model="review",embedding_model="embed")
        self.responses=iter(responses); self.limits=[]
    def _request(self,path,payload=None):
        self.limits.append(payload.get("options",{}).get("num_predict"))
        return next(self.responses)

class OllamaTests(unittest.TestCase):
    def test_incomplete_json_retries_with_larger_limit(self):
        client=Stub([{"response":"not json","done":False},{"response":'{"findings":[]}',"done":True}])
        data,_=client.generate_json("review",100)
        self.assertEqual(data,{"findings":[]}); self.assertEqual(client.limits,[100,200])
    def test_malformed_json_fails_cleanly(self):
        client=Stub([{"response":"bad"},{"response":"still bad"}])
        with self.assertRaises(OllamaError): client.generate_json("review")
    def test_embedding_dimensions_validated(self):
        client=Stub([{"embeddings":[[1,2],[1]]}])
        with self.assertRaises(OllamaError): client.embed(["a","b"])

if __name__ == "__main__": unittest.main()
