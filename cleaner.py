import time
import requests
import zipfile
import io
import json
import xml.etree.ElementTree as ET

from request import RestRequest
from helpers.api_helper import APIHelper
from helpers.bundle_analyzer import BundleAnalyzer
from utils.logger import Logger


class ApigeeOrganizationCleaner():
    def __init__(self, imp_proxies: list, hierarchy: object, domain: str = "apigee.googleapis.com", 
                 organization: str = "gcp101027-apigeex"):
        self.imp_proxies = imp_proxies
        self.hierarchy = hierarchy
        self.domain = domain
        self.organization = organization
        self.main_url = f"https://{self.domain}/v1/organizations/{organization}"
        
        self.request = RestRequest()
        self.logger = Logger(__class__.__name__)
        self.api_helper = APIHelper()
        self.bundle_analyzer = BundleAnalyzer()

    # --- HELPERS ---
    def is_important_proxy(self, proxy:str) -> bool:
        return proxy in self.imp_proxies

    # --- PROXIES ---
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
                    self.api_helper.wait_for_undeploy(env_name, "apis", proxy["name"], revision, self.main_url)  
            
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

    # --- SHAREDFLOWS ---
    def delete_sharedflows(self):
        self.logger.log("--- Processing SHAREDFLOWS ---")
        
        sharedflows = self.hierarchy.get("sharedflow", [])
        for sharedflow in sharedflows[:]:
            self.logger.log(f"Processing sharedflow {sharedflow["name"]}")

            if len(sharedflow["proxy"]) > 0:
                self.logger.log(f"SharedFlow {sharedflow['name']} is used by existing proxies. Skipping.")
                continue
            
            # Detach from FlowHooks            
            envs_attached = self.get_sharedflow_flowhook_attachments(sharedflow["name"])
            for env_name in envs_attached.get("envs_to_detach"):
                self.detach_flowhook(env_name, sharedflow["name"])

            can_delete = envs_attached.get("can_delete")
            if not can_delete:
                self.logger.log(f"SharedFlow '{sharedflow['name']}' is used in a LIVE environment flowhook. Skipping.")
                continue

            # Undeploying
            revisions = sharedflow.get("revisions", {})
            for revision, details in revisions.items():
                env_name = details.get("environment")
                revision = revision.split("|")[0]
                if env_name:
                    self.logger.log(f"Undeploying SharedFlow {sharedflow['name']} rev {revision} from {env_name}")
                    url = f"{self.main_url}/environments/{env_name}/sharedflows/{sharedflow['name']}/revisions/{revision}/deployments"
                    self.request.delete(url) # -------------------- PROTECTION -----------------------
                    self.api_helper.wait_for_undeploy(env_name, "sharedflows", sharedflow["name"], revision, self.main_url)  

            # Check and delete all posible sharedFlow dependencies
            self.delete_shareflow_dependencies(sharedflow)

            self.logger.log(f"Deleting sharedflow {sharedflow["name"]}")
            url = f"{self.main_url}/sharedflows/{sharedflow['name']}"
            if self.api_helper.api_delete(url, f"SharedFlow {sharedflow["name"]}"):
                sharedflows.remove(sharedflow)

    def detach_flowhook(self, env_name, sf_name):
        self.logger.log(f"Detaching {sf_name} from FlowHooks in {env_name}")
        env_data = next((e for e in self.hierarchy["environments"] if e["name"] == env_name), None)
        if not env_data: return
       
        hooks = ["PreProxyFlowHook", "PostProxyFlowHook", "PreTargetFlowHook", "PostTargetFlowHook"]   
        for hook_name in hooks:
            hook_in_json = next((h for h in env_data.get("flowhook", []) if h["name"] == hook_name), None)
            
            if hook_in_json and hook_in_json.get("sharedflow") == sf_name:
                url = f"{self.main_url}/environments/{env_name}/flowhooks/{hook_name}"
                self.request.delete(url) # -------------------- PROTECTION -----------------------
                hook_in_json["sharedflow"] = ""

    def get_sharedflow_flowhook_attachments(self, sf_name: str) -> object:
        self.logger.log(f"Checking FlowHook attachments for SharedFlow {sf_name}...")
        env_to_detach = []
        is_blocking_deletion = False

        for env in self.hierarchy["environments"]:
            env_flowhooks = env["flowhook"]
            
            is_attached_in_this_env = False
            for flowhook in env_flowhooks:
                if flowhook.get("sharedflow") == sf_name:
                    is_attached_in_this_env = True
                    break
            
            if is_attached_in_this_env:
                has_proxies = len(env.get("proxy", [])) > 0
                if has_proxies:
                    is_blocking_deletion = True
                else:
                    env_to_detach.append(env["name"])

        return {"can_delete": not is_blocking_deletion, "envs_to_detach": list(set(env_to_detach))}

    def delete_shareflow_dependencies(self, sharedflow: object):
        self.logger.log(f"Deleting dependencies of SharedFlow {sharedflow['name']}...")
        for env in self.hierarchy["environments"]:
            env_sharedflows = env["sharedflow"]
            if sharedflow["name"] in env_sharedflows:
                env_sharedflows.remove(sharedflow["name"])

    # --- API PRODUCTS ---
    def delete_api_products(self):
        self.logger.log("--- Processing API PRODUCTS ---")
        self.api_products_clean_up()

        apiproducts = self.hierarchy.get("apiproduct")
        for apip in apiproducts[:]:
            self.logger.log(f"Processing API Product {apip["name"]}...")
            if len(apip["proxy"]) > 0:
                self.logger.log(f"API product: {apip["name"]} has active proxies. Skipping.")
                continue
            
            self.logger.log(f"Detaching API Product {apip["name"]} from Apps...")
            apps_using = apip.get("app", [])
            for app_name in apps_using:
                self.detach_product_from_app(app_name, apip["name"])

            self.logger.log(f"Deleting API Product {apip["name"]}...")
            url = f"{self.main_url}/apiproducts/{apip["name"]}"
            if self.api_helper.api_delete(url, f"API Product {apip["name"]}"):
                apiproducts.remove(apip)

    def detach_product_from_app(self, app_name, product_name):
        app_obj = next((a for a in self.hierarchy["app"] if a["name"] == app_name), None)
        if not app_obj: return

        dev_email = app_obj["developer"]
        
        url = f"{self.main_url}/developers/{dev_email}/apps/{app_name}"
        app_details = self.request.get(url).json()

        self.logger.log(f"Revoking/Removing product {product_name} from App {app_name} (Dev: {dev_email})")

        for cred in app_details.get("credentials",[]):
            cred_products = cred.get("apiProducts",[])
            consKey = cred["consumerKey"]

            is_product_exits = any(apip.get("apiproduct") == product_name for apip in cred_products)
            if is_product_exits:
                url = f"{self.main_url}/developers/{dev_email}/apps/{app_name}/keys/{consKey}/apiproducts/{product_name}"
                self.request.delete(url)  #--- PROTECTION -------------------------
            
        # Clean JSON
        if product_name in app_obj["apiproduct"]:
            app_obj["apiproduct"].remove(product_name)

    def api_products_clean_up(self):
        existing_proxy_names = [p["name"] for p in self.hierarchy["proxy"]]
        for apip in self.hierarchy["apiproduct"]:
            apip["proxy"] = [p for p in apip["proxy"] if p in existing_proxy_names]

    # --- DEVELOPERS AND APPS
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

    # --- KEY VALUE MAPS ---
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

                self.bundle_analyzer.scan_bundle_for_resources(url, zip_folder_prefix, BundleAnalyzer.parse_policy_for_kvm, used_kvms, f"Proxy {proxy_name}")

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
                
                self.bundle_analyzer.scan_bundle_for_resources(url, zip_folder_prefix, BundleAnalyzer.parse_policy_for_kvm, used_kvms, f"SharedFlow {sf_name}")

        self.logger.log(f"Found {len(used_kvms)} unique KVMs used in code: {used_kvms}")
        return used_kvms
    
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
    
    def detach_from_instances(self, env_name):
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
        
    # --- CUSTOM REPORTS ---
    def delete_custom_reports(self):
        self.logger.log("--- Processing CUSTOM REPORTS ---")
        url = f"{self.main_url}/reports"
        response = self.request.get(url)

        reports = response.json().get("qualifier", [])
        for report in reports:
            report_name = report.get("name") 
            self.logger.log(f"Processing Custom Report {report_name}...")
            self.logger.log(f"Deleting Custom Report {report_name}...")
            url = f"{self.main_url}/reports/{report_name}"
            self.api_helper.api_delete(url, f"Custom report {report_name}") # --- PROTECTION ---
    
    # --- DATA COLLECTORS ---
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
                
                self.bundle_analyzer.scan_bundle_for_resources(url, zip_folder_prefix,BundleAnalyzer.parse_policy_for_datacollector, used_dcs, f"Proxy {proxy_name}")

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
                
                self.bundle_analyzer.scan_bundle_for_resources(url, zip_folder_prefix,BundleAnalyzer.parse_policy_for_datacollector, used_dcs, f"SharedFlow {sf_name}")

        self.logger.log(f"Found {len(used_dcs)} unique DataCollectors used in code: {used_dcs}")
        return used_dcs

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
    
    # --- INSTANCES ---
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
      
    def clean(self):
        self.delete_proxies()
        self.delete_sharedflows()
        self.delete_api_products()
        self.delete_developer_and_apps()
        self.delete_kvms()
        self.delete_environments()
        self.delete_custom_reports()
        self.delete_data_collectors()
        self.delete_env_groups()
        # self.delete_instances()
        
        self.logger.log("--- ORGANIZATIONS CLEANUP COMPLETED ---")

        with open("cleaner_output.json", "w") as file:
            json.dump(self.hierarchy, file, indent=4)

        