from .base_cleaner import BaseCleaner

class EnvGroupCleaner(BaseCleaner):
    def __init__(self, hierarchy: object, main_url: str):
        super().__init__(hierarchy, main_url)

    def delete(self):
        self.delete_env_groups()

    # --- ENV GROUPS ---
    def delete_env_groups(self):
        self.logger.log("--- Processing ENV GROUPS ---")
        url = f"{self.main_url}/envgroups?pageSize=100"
        response = self.request.get(url)

        env_groups = response.json().get("environmentGroups", [])
        for env_group in env_groups:
            self.logger.log(f"Processing Env Group {env_group["name"]}...")
            if not self.is_env_group_empty(env_group):
                self.logger.log(f"Skipping Env Group {env_group["name"]}: not empty.")
                continue
            
            self.logger.log(f"Deleting Env Group {env_group["name"]}...")
            url = f"{self.main_url}/envgroups/{env_group["name"]}"
            self.api_helper.api_delete(url, f"Env Group {env_group["name"]}") # --- PROTECTION ---
            
    def is_env_group_empty(self, env_group: object):
        url = f"{self.main_url}/envgroups/{env_group["name"]}/attachments"
        response = self.request.get(url)
        env_att = response.json().get("environmentGroupAttachments", [])
        return len(env_att) < 1