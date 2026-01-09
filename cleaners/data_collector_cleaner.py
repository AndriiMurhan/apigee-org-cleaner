from .base_cleaner import BaseCleaner
from helpers.bundle_analyzer import BundleAnalyzer

class DataCollectorCleaner(BaseCleaner):
    def __init__(self, hierarchy: object, main_url: str):
        super().__init__(hierarchy, main_url)
        self.bundle_analyzer = BundleAnalyzer()
        
    def delete(self):
        self.delete_data_collectors()

    #--- DATA COLLECTOR ---
    def delete_data_collectors(self):
        self.logger.log("--- Processing DATA COLLECTORS ---")
        
        url = f"{self.main_url}/datacollectors?pageSize=100"
        response = self.request.get(url)
        datacollectors = response.json().get("dataCollectors", [])

        if len(datacollectors) < 1:
            return

        safe_data_collectors = self.find_data_collectors_used_in_proxies_and_sharedflow()
        
        for dc in datacollectors:
            dc_name = dc["name"]
            self.logger.log(f"Processing DataCollector {dc_name}...")
            if dc_name in safe_data_collectors:
                self.logger.log(f"Datacollector: {dc_name} has active proxies. Skipping.")
                continue
            
            url = f"{self.main_url}/datacollectors/{dc_name}"
            self.api_helper.api_delete(url, f"Datacollector {dc_name}") # --- PROTECTION ---

    def find_data_collectors_used_in_proxies_and_sharedflow(self):
        self.logger.log("Scanning for DataCollector usage in Proxies and SharedFlows...")

        used_dcs = set()
        proxies = self.hierarchy.get("proxy", [])
        self.logger.log(f"Starting DataCollector analysis for {len(proxies)} proxies...")
        
        for proxy in proxies:
            proxy_name = proxy["name"]
            revisions = proxy.get("revisions", {})
            
            for revision in list(revisions.keys()):
                revision = revision.split("|")[0]
                self.logger.log(f"Checking Proxy {proxy_name} revision {revision}...") 
                url = f"{self.main_url}/apis/{proxy_name}/revisions/{revision}?format=bundle"
                zip_folder_prefix = "apiproxy/policies/"
                
                self.bundle_analyzer.scan_bundle_for_resources(url, zip_folder_prefix,self.bundle_analyzer.parse_policy_for_datacollector, used_dcs, f"Proxy {proxy_name}")

        sharedflows = self.hierarchy.get("sharedflow", [])
        self.logger.log(f"Starting DataCollector analysis for {len(sharedflows)} shared flows...")
        
        for sf in sharedflows:
            sf_name = sf["name"]
            revisions = sf.get("revisions", {})
            
            for revision in list(revisions.keys()):
                revision = revision.split("|")[0]
                self.logger.log(f"Checking sharedflow {sf_name} revision {revision}...") 
                url = f"{self.main_url}/sharedflows/{sf_name}/revisions/{revision}?format=bundle"
                zip_folder_prefix = "sharedflowbundle/policies/"
                
                self.bundle_analyzer.scan_bundle_for_resources(url, zip_folder_prefix,self.bundle_analyzer.parse_policy_for_datacollector, used_dcs, f"SharedFlow {sf_name}")

        self.logger.log(f"Found {len(used_dcs)} unique DataCollectors used in code: {used_dcs}")
        return used_dcs