from .base_cleaner import BaseCleaner

class ProxyCleaner(BaseCleaner):
    def __init__(self, imp_proxies: list, hierarchy: object, main_url: str):
        super().__init__(hierarchy, main_url)
        self.imp_proxies = imp_proxies

    def is_important_proxy(self, proxy:str) -> bool:
        return proxy in self.imp_proxies
    
    def delete(self):
        self.delete_proxies()

    def delete_proxies(self):
        self.logger.log("--- Processing PROXIES ---")
        
        proxies = self.hierarchy.get("proxy", [])
        for proxy in proxies[:]:
            self.logger.log(f"Processing proxy {proxy["name"]}...")
            if self.is_important_proxy(proxy["name"]):  
                self.logger.log(f"Skipping protected proxy: {proxy["name"]}")              
                continue
            
            # Undeploy Revisions
            revisions = proxy.get("revisions", {})
            for revision, details in revisions.items():
                env_name = details.get("enviroment")
                revision = revision.split("|")[0]
                if env_name:
                    self.logger.log(f"Undeploying {proxy['name']} rev {revision} from {env_name}...")
                    url = f"{self.main_url}/environments/{env_name}/apis/{proxy["name"]}/revisions/{revision}/deployments"       
                    self.request.delete(url) # - --------------------- PROTECTION -----------------------
                    self.api_helper.wait_for_undeploy(env_name, "apis", proxy["name"], revision, self.main_url)  # -------------------- PROTECTION -----------------------
            
            self.delete_proxy_dependencies(proxy["name"])
            
            self.logger.log(f"Deleting proxy {proxy["name"]}...")
            url = f"{self.main_url}/apis/{proxy["name"]}"
            if self.api_helper.api_delete(url,f"Proxy {proxy["name"]}"):
                proxies.remove(proxy)

    def delete_proxy_dependencies(self, proxy_name: str):
        self.logger.log(f"Deleting dependencies of {proxy_name}...")
        
        for env in self.hierarchy.get("environments", []):
            env_proxies = env["proxy"]
            while proxy_name in env_proxies:
                env_proxies.remove(proxy_name)

        for sh in self.hierarchy.get("sharedflow", []):
           sh_proxies = sh["proxy"]
           while proxy_name in sh_proxies:
               sh_proxies.remove(proxy_name)

        for apip in self.hierarchy.get("apiproduct", []):
            apip_proxies = apip["proxy"]
            while proxy_name in apip_proxies:
                apip_proxies.remove(proxy_name)