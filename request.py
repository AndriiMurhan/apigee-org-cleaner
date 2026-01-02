import requests
from auth2 import Auth2Token
class RestRequest():
    def __init__(self):
        self.aouth2 = Auth2Token("key.pem")
        self.aouth2.generate_new_access_token()
        self.access_token = self.aouth2.get_access_token()
        self.headers = {"Authorization": "Bearer "+ self.access_token}
    def updateCrediatianals(self):
        self.aouth2.generate_new_access_token()
        self.access_token = self.aouth2.get_access_token()
        self.headers = {"Authorization": "Bearer "+ self.access_token}
    def get(self, url, stream=False):
        retry = 0
        response = requests.get(url,headers=self.headers,stream=stream)
        while response.status_code == 401:
            self.updateCrediatianals()
            response = requests.get(url,headers=self.headers)
            retry +=1
            if retry == 3:
                break
        return response
    
    def delete(self, url, stream=False):
        retry = 0
        response = requests.delete(url,headers=self.headers,stream=stream)
        
        while response.status_code == 401:
            self.updateCrediatianals()
            response = requests.delete(url,headers=self.headers, stream=stream)
            retry += 1
            if retry == 3:
                break
        
        return response    