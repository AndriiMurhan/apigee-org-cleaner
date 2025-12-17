import requests
import json
import zipfile
import xml.etree.ElementTree as ET
from auth2 import Auth2Token
from request import RestRequest
class ExtracterApigeeResources():
    def __init__(self,domain="apigee.googleapis.com", 
                 organization="gcp101027-apigeex"):
        self.request = RestRequest()
        self.domain = domain
        self.main_url = f"https://{self.domain}/v1/organizations/"
        self.organization = organization
    def get_last_number_deployed_revision_proxy(self, name_proxy):
        response = self.request.get(f"{self.main_url}{self.organization}/apis/{name_proxy}/deployments")
        if (len(json.loads(response.text)) > 0 ):
            revisions = json.loads(response.text)["deployments"] # get all deployed revisions
            list_revisions = []
            for revision in revisions:
                list_revisions.append(int(revision['revision']))
            final_revision = max(list_revisions)
            return final_revision
        else:
            return -1
    def download_file(self,url):
        # NOTE the stream=True parameter below
        with self.request.get(url,stream=True) as r:
            r.raise_for_status()
            with open("temprorary.zip", 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): 
                    # If you have chunk encoded response uncomment if
                    # and set chunk_size parameter to None.
                    #if chunk: 
                    f.write(chunk)
    def get_sharedflows(self,url):
        sharedflows = []
        self.download_file(url)
        with zipfile.ZipFile("temprorary.zip") as arhive:
            list_names = [object for object in arhive.namelist() if "apiproxy/policies/" in str(object)]
            if len(list_names) > 0:
                if "apiproxy/policies/" in list_names:
                    list_names.remove("apiproxy/policies/")
                    policy_list = [str(object).removeprefix("apiproxy/policies/") for object in list_names]
                    flowcallout_list = [policy for policy in policy_list if "FC-" in policy]
                    if len(flowcallout_list) > 0:
                        for flowcallout in flowcallout_list:
                            with arhive.open("apiproxy/policies/"+flowcallout) as myfile:
                                root_element = ET.fromstring(myfile.read())
                                for sharedflow in root_element.findall('SharedFlowBundle'): 
                                    sharedflows.append(sharedflow.text)
        return sharedflows
    def get_proxies(self,includeRevisions=False,includeMetaData=False):
        response = []
        list_all_names_proxy = json.loads(self.request.get(f"{self.main_url}{self.organization}/apis?includeRevisions={includeRevisions}&includeMetaData={includeMetaData}").text)["proxies"] 
        for proxy in list_all_names_proxy:
            record = {}
            record["type"] = "proxy"
            record["name"] = proxy["name"]
            revision = self.get_last_number_deployed_revision_proxy(proxy["name"])
            if revision == -1:
                resp = json.loads(self.request.get(f"{self.main_url}{self.organization}/apis/{proxy["name"]}",).text)
                revision = resp["latestRevisionId"]
            url = f"{self.main_url}{self.organization}/apis/{proxy["name"]}/revisions/{revision}?format=bundle"
            list_sharedflow = self.get_sharedflows(url)
            record["sharedflow"] = list_sharedflow
            response.append(record)
            if len(response) == 20:
                break
        with open("result.json", "w") as result:
            result.write(json.dumps(response))
        print("proxy was done")
    def get_proxy(self,name,includeRevisions=False,includeMetaData=False):
        response = self.request.get(f"{self.main_url}{self.organization}/apis/{name}")
        proxies_json = json.loads(response.text)
        return proxies_json
if __name__ == "__main__":
   extracter = ExtracterApigeeResources()
   data1 = extracter.get_proxies(includeRevisions=True)


