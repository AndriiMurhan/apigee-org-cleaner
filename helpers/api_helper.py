import time
from request import RestRequest
from utils.logger import Logger

class APIHelper:
    def __init__(self):
        self.request = RestRequest()
        self.logger = Logger(__class__.__name__)

    def api_delete(self, url: str, resource_name: str) -> bool:
        # self.logger.log(f"Successfully deleted: {resource_name}")
        # return True # --- PROTECTION -------------------------------

        try:
            resp = self.request.delete(url)

            if resp.status_code in [200,204]:
                self.logger.log(f"Successfully deleted: {resource_name}")
                return True
            elif resp.status_code == 404:
                self.logger.log(f"Resource was not found! It's already gone: {resource_name}")
                return True
            else:
                print(f"Error deleting {resource_name}: {resp.text}")
                return False
        except Exception as e:
            self.logger.log(f"Exception deleting {resource_name}: {e}")

    def wait_for_undeploy(self, env: str, resource_type: str, name: str, 
                          revision: str,  base_url: str, timeout: int = 300) -> bool:
        start_time = time.time()
        self.logger.log(f"Waiting for {name} (rev {revision}) to undeploy from {env}...")
        url = f"{base_url}/environments/{env}/{resource_type}/{name}/revisions/{revision}/deployments"

        while time.time() - start_time < timeout:
            try:
                response = self.request.delete(url)
                # self.logger.log(f"[DEBUG] response: {response.json()}")
                
                if response.status_code == 404:
                    self.logger.log(f"{name} undeployed successfully")
                    return True
                
                if response.status_code == 200:
                    data = response.json()
                    if not data or data.get('state') != 'DEPLOYED' or data.get('state') != "IN PROGRESS":
                        self.logger.log(f"{name} undeployed successfully (status changed).")
                        return True
                    
            except Exception as e:
                self.logger.log(f"Error checking status: {e}")
            
            time.sleep(2)

        self.logger.log(f"Timout waiting for undeploy: {name}")
        return False
    
    def wait_for_operation(self, operation_name: str, domain: str, timeout: int = 600) -> bool:
        start_time = time.time()
        self.logger.log(f"Waiting for operation {operation_name} to complete...")

        url = f"https://{domain}/v1/{operation_name}"
        while time.time() - start_time < timeout:
            try:
                response = self.request.get(url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("done") is True:
                        if "error" in data:
                            self.logger.log(f"Operation failed: {data["error"]}")
                            return False
                        
                        self.logger.log(f"Operation completed successfully.")
                        return True
                else:
                    self.logger.log(f"Error checking operation status: {response.status_code}")
            except Exception as e:
                self.logger.log(f"Error checking attachment: {e}")
            
            time.sleep(5)
        
        self.logger.log(f"Timeout waiting for operation.")
        return False