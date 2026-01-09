from .base_cleaner import BaseCleaner

class DevAndAppCleaner(BaseCleaner):
    def __init__(self, hierarchy: object, main_url: str):
        super().__init__(hierarchy, main_url)
    
    def delete(self):
        self.delete_developer_and_apps()

    def delete_developer_and_apps(self):
        self.logger.log("--- Processing DEVS & APPS ---")
        
        developers = self.hierarchy.get("developers", [])
        for dev in developers[:]:
            self.logger.log(f"Processing Developer {dev['email']}...")

            dev_apps = dev.get("app", [])
            for app_name in dev_apps[:]:
                full_app = next((a for a in self.hierarchy["app"] if a["name"] == app_name), None)

                if full_app and len(full_app["apiproduct"]) < 1:
                    self.logger.log(f"Deleting App {app_name} (no products)")
                    url = f"{self.main_url}/developers/{dev['email']}/apps/{app_name}"
                    if self.api_helper.api_delete(url, f"App {app_name}"):
                        dev_apps.remove(app_name)
                        if full_app in self.hierarchy["app"]:
                            self.hierarchy["app"].remove(full_app)

                if len(dev_apps) < 1:
                    self.logger.log(f"Deleting Developer {dev['email']} (no apps)")
                    url = f"{self.main_url}/developers/{dev["email"]}"
                    if self.api_helper.api_delete(url, f"Developer {dev["email"]}"):
                        developers.remove(dev)