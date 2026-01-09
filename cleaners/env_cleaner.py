from .base_cleaner import BaseCleaner

class EnvironmentCleaner(BaseCleaner):
    def __init__(self, hierarchy: object, main_url: str, domain: str = "apigee.googleapis.com"):
        super().__init__(hierarchy, main_url)
        self.domain = domain

    def delete(self):
        self.delete_environments()

    # --- ENVIRONMENTS ---
    def delete_environments(self):
        self.logger.log("--- Processing ENVIRONMENTS ---")
        
        envs = self.hierarchy["environments"]
        for env in envs[:]:
            self.logger.log(f"Processing Env {env["name"]}...")

            has_proxies = len(env["proxy"]) > 0
            has_sharedflows = len(env["sharedflow"]) > 0 
            if has_proxies or has_sharedflows:
                self.logger.log(f"Skipping Env {env["name"]}: not empty.")
                continue
            
            self.detach_from_instances(env["name"])

            self.logger.log(f"Deleting Env {env["name"]}...")
            url = f"{self.main_url}/environments/{env["name"]}"
            if self.api_helper.api_delete(url, f"Environment {env["name"]}"):
                envs.remove(env)
    
    def detach_from_instances(self, env_name: str):
        self.logger.log(f"Detaching Env {env_name} from Instances...")
        url = f"{self.main_url}/instances?pageSize=100"
        response = self.request.get(url)
        instances = response.json().get("instances", [])

        for instance in instances:
            inst_name = instance["name"]
            url = f"{self.main_url}/instances/{inst_name}/attachments?pageSize=100"
            response = self.request.get(url)
            attachments = response.json().get("attachments", [])
            attachment_obj = next((a for a in attachments if a["environment"] == env_name), None)
            if attachment_obj:
                self.logger.log(f"Detaching Env {env_name} from Instance {inst_name}...")
                url = f"{self.main_url}/instances/{inst_name}/attachments/{attachment_obj["name"]}"
                resp = self.request.delete(url) # --------- PROTECTION ----------
                operation_name = resp.json().get("name")
                if self.api_helper.wait_for_operation(operation_name, self.domain):
                    self.logger.log(f"Succesfully deleted: Attachment env: {env_name} to instance: {inst_name}")