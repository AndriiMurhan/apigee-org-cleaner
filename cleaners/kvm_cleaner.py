from .base_cleaner import BaseCleaner
from helpers.bundle_analyzer import BundleAnalyzer

class KVMCleaner(BaseCleaner):
    def __init__(self, hierarchy: object, main_url: str):
        super().__init__(hierarchy, main_url)
        self.bundle_analyzer = BundleAnalyzer()

    def delete(self):
        self.delete_kvms()

    def delete_kvms(self):
        self.logger.log("--- Processing KVMs ---")
        safe_kvms = self.find_kvms_used_in_proxies_and_sharedflows()

        # Org kvms
        org_kvm = self.hierarchy["organization_kvm"]
        for kvm in org_kvm[:]:
            if kvm not in safe_kvms:
                self.logger.log(f"Deleting Org KVM {kvm}...")
                url = f"{self.main_url}/keyvaluemaps/{kvm}"
                if self.api_helper.api_delete(url, f"Org KVM {kvm}"):
                    org_kvm.remove(kvm)

        # Env kvms
        envs = self.hierarchy["environments"]
        for env in envs:
            env_kvm = env["kvm"]
            for kvm in env_kvm[:]:
                if kvm not in safe_kvms:
                    self.logger.log(f"Deleting Env KVM {kvm} in {env['name']}...")
                    url = f"{self.main_url}/environments/{env['name']}/keyvaluemaps/{kvm}"
                    if self.api_helper.api_delete(url, f"Env KVM {kvm} in {env["name"]}"):
                        env_kvm.remove(kvm)

    def find_kvms_used_in_proxies_and_sharedflows(self):
        self.logger.log("Scanning for KVM usage in Proxies and SharedFlows...")
        used_kvms = set()
        proxies = self.hierarchy["proxy"]
        
        self.logger.log(f"Starting static analysis of {len(proxies)} proxies...")
        for proxy in proxies:
            proxy_name = proxy["name"]
            
            revisions = proxy["revisions"]
            for revision in list(revisions.keys()):
                revision = revision.split("|")[0]
                self.logger.log(f"Checking {proxy_name} revision {revision}...")
                url = f"{self.main_url}/apis/{proxy["name"]}/revisions/{revision}?format=bundle"
                zip_folder_prefix = "apiproxy/policies/"

                self.bundle_analyzer.scan_bundle_for_resources(url, zip_folder_prefix, self.bundle_analyzer.parse_policy_for_kvm, used_kvms, f"Proxy {proxy_name}")

        sharedflows = self.hierarchy.get("sharedflow", [])
        self.logger.log(f"Starting static analysis of {len(sharedflows)} sharedflows...")
        for sf in sharedflows:
            sf_name = sf["name"]            
            revisions = sf.get("revisions", {})
            
            for revision in list(revisions.keys()):
                revision = revision.split("|")[0]
                self.logger.log(f"Checking SharedFlow {sf_name} revision {revision}...")
                url = f"{self.main_url}/sharedflows/{sf_name}/revisions/{revision}?format=bundle"
                zip_folder_prefix = "sharedflowbundle/policies/"
                
                self.bundle_analyzer.scan_bundle_for_resources(url, zip_folder_prefix, self.bundle_analyzer.parse_policy_for_kvm, used_kvms, f"SharedFlow {sf_name}")

        self.logger.log(f"Found {len(used_kvms)} unique KVMs used in code: {used_kvms}")
        return used_kvms