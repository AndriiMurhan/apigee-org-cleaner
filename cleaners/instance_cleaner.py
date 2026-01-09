from .base_cleaner import BaseCleaner

class InstanceCleaner(BaseCleaner):
    def __init__(self, hierarchy: object, main_url: str):
        super().__init__(hierarchy, main_url)
    
    def delete(self):
        self.delete_instances()

    def delete_instances(self):
        self.logger.log("--- Processing INSTANCES ---")
        url = f"{self.main_url}/instances"
        response = self.request.get(url)

        instances = response.json().get("instances", [])
        for inst in instances:
            self.logger.log(f"Processing Instance {inst["name"]}...")

            # Check if has any attachments
            if self.has_inst_attachemnts(inst):
                self.logger.log(f"Skipping instance {inst["name"]}: not empty.")
                continue
            
            self.logger.log(f"Deleting Instance {inst["name"]}...")
            url = f"{self.main_url}/instances/{inst["name"]}"
            self.api_helper.api_delete(url, f"Instance {inst["name"]}")

    def has_inst_attachemnts(self, instance: object):
        url = f"{self.main_url}/instances/{instance["name"]}/attachments"
        response = self.request.get(url)

        inst_atts = response.json().get("attachments", [])
        return len(inst_atts) > 0