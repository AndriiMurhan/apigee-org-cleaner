from datetime import datetime
import time
from request import RestRequest
import xml.etree.ElementTree as ET
import requests
import zipfile
import io
import json

class ApigeeOrganizationCleaner():
    def __init__(self, imp_proxies: list, hierarchy: object, domain: str = "apigee.googleapis.com", 
                 organization: str = "gcp101027-apigeex"):
        self.imp_proxies = imp_proxies
        self.hierarchy = hierarchy
        self.domain = domain
        self.organization = organization
        self.main_url = f"https://{self.domain}/v1/organizations/{organization}"
        
        self.request = RestRequest()

    # --- HELPERS ---
    def log(self, message):
        current_time = datetime.now().strftime("%H:%M:%S")
        class_name = self.__class__.__name__
        print(f"[{current_time}] {class_name} - {message}")

    def api_delete(self, url, resource_name):
        self.log(f"Successfully deleted: {resource_name}")
        return True # --- PROTECTION -------------------------------

        try:
            resp = self.request.delete(url)

            if resp.status_code in [200, 204]:
                self.log(f"Successfully deleted: {resource_name}")
                return True
            elif resp.status_code == 404:
                self.log(f"Resource was not found! It's already gone: {resource_name}")
                return True
            else:
                print(f"Error deleting {resource_name}: {resp.text}")
                return False
        except Exception as e:
            self.log(f"Exception deleting {resource_name}: {e}")

    def wait_for_undeploy(self, env, resource_type, name, revision, timeout=60):
        start_time = time.time()
        self.log(f"Waiting for {name} (rev {revision}) to undeploy from {env}...")
        url = f"{self.main_url}/environments/{env}/{resource_type}/{name}/revisions/{revision}/deployments"

        while time.time() - start_time < timeout:
            try:
                response = self.request.delete(url)

                if response.status_code == 404:
                    self.log(f"{name} undeployed successfully")
                    return True
                
                if response.status_code == 200:
                    data = response.json()
                    if not data or data.get('state') != 'DEPLOYED' or data.get('state') != "IN PROGRESS":
                        self.log(f"{name} undeployed successfully (status changed).")
                        return True
                    
            except Exception as e:
                self.log(f"Error checking status: {e}")
            
            time.sleep(2)

        self.log(f"Timout waiting for undeploy: {name}")
        return False
    
    def is_important_proxy(self, proxy:str) -> bool:
        return proxy in self.imp_proxies

    # --- PROXIES ---
    # Algorithm
    # 1. Check if proxy is in the filter list
    #   a. If in the list then skip it
    # 2. Iterate though revisions and undeploy every revision from its enviroment
    # 3. When every revision is undeployed, remove proxy dependenies in the hierarchy and organization
    # 4. Remove proxy itself from hierarchy.json and organization (DELETE Request)
    def delete_proxies(self):
        self.log("--- Processing PROXIES ---")
        
        proxies = self.hierarchy.get("proxy", [])
        for proxy in proxies[:]:
            if self.is_important_proxy(proxy["name"]):  
                self.log(f"Skipping protected proxy: {proxy["name"]}")              
                continue
            
            # Undeploy Revisions
            revisions = proxy.get("revisions", {})
            for revision, details in revisions.items():
                env_name = details.get("enviroment")
                if env_name:
                    self.log(f"Undeploying {proxy['name']} rev {revision} from {env_name}...")
                    url = f"{self.main_url}/environments/{env_name}/apis/{proxy["name"]}/revisions/{revision}/deployments"       
                    self.request.delete(url) #- --------------------- PROTECTION -----------------------
                    self.wait_for_undeploy(env_name, "apis", proxy["name"], revision)  
            
            self.delete_proxy_dependencies(proxy["name"])
            
            url = f"{self.main_url}/apis/{proxy["name"]}"
            if self.api_delete(url,f"Proxy {proxy["name"]}"):
                proxies.remove(proxy)

    def delete_proxy_dependencies(self, proxy_name: str):
        self.log(f"Deleting dependencies of {proxy_name}...")
        
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
    # Algorithm
    # 1. Check if any not deleted proxy has attached the proxy to it
    #   a. If has than we skip it
    # 2. Check if the sharedflow is attached to any flowhook in valid enviroments
    #   b. If it is then iterate thought env list and detach from it
    # 3. Undeploy sharedflow from enviremont
    # 4. Remove all possible dependencies with other resources
    # 5. Remove sharedFlow itself.
    def delete_sharedflows(self):
        self.log("--- Processing SHAREDFLOWS ---")
        
        sharedflows = self.hierarchy.get("sharedflow", [])
        for sharedflow in sharedflows[:]:
            # Check if shared flow is attached to any proxy
            if len(sharedflow["proxy"]) > 0:
                self.log(f"SharedFlow {sharedflow['name']} is used by existing proxies. Skipping.")
                continue
            
            # Detach from FlowHooks
            envs_attached = self.get_sharedflow_flowhook_attachments(sharedflow["name"])
            for env_name in envs_attached:
                self.detach_flowhook(env_name, sharedflow["name"])

            # Undeploying
            revisions = sharedflow.get("revisions", {})
            for revision, details in revisions.items():
                env_name = details.get("environment")
                if env_name:
                    self.log(f"Undeploying SharedFlow {sharedflow['name']} rev {revision} from {env_name}")
                    url = f"{self.main_url}/environments/{env_name}/sharedflows/{sharedflow['name']}/revisions/{revision}/deployments"
                    self.request.delete(url) # -------------------- PROTECTION -----------------------
                    self.wait_for_undeploy(env_name, "sharedflows", sharedflow["name"], revision, 120)  

            # Check and delete all posible sharedFlow dependencies
            self.delete_shareflow_dependencies(sharedflow)

            url = f"{self.main_url}/sharedflows/{sharedflow['name']}"
            if self.api_delete(url, f"SharedFlow {sharedflow["name"]}"):
                sharedflows.remove(sharedflow)

    def detach_flowhook(self, env_name, sf_name):
        self.log(f"Detaching {sf_name} from FlowHooks in {env_name}")
        env_data = next((e for e in self.hierarchy["environments"] if e["name"] == env_name), None)
        if not env_data: return
       
        hooks = ["PreProxyFlowHook", "PostProxyFlowHook", "PreTargetFlowHook", "PostTargetFlowHook"]   
        for hook_name in hooks:
            hook_in_json = next((h for h in env_data.get("flowhook", []) if h["name"] == hook_name), None)
            
            if hook_in_json and hook_in_json.get("sharedflow") == sf_name:
                url = f"{self.main_url}/environments/{env_name}/flowhooks/{hook_name}"
                self.request.delete(url) # -------------------- PROTECTION -----------------------
                hook_in_json["sharedflow"] = ""

    def get_sharedflow_flowhook_attachments(self, sf_name: str) -> list:
        envs_with_sharedflow = []

        for env in self.hierarchy["environments"]:
            env_flowhooks = env["flowhook"]
            for flowhook in env_flowhooks:
                if flowhook.get("sharedflow") == sf_name:     
                    # Check if environment is invalid(doesn't have any proxies)
                    if len(env["proxy"]) < 1:
                        envs_with_sharedflow.append(env["name"])
        
        return list(set(envs_with_sharedflow))

    def delete_shareflow_dependencies(self, sharedflow: object):
        for env in self.hierarchy["environments"]:
            env_sharedflows = env["sharedflow"]
            if sharedflow["name"] in env_sharedflows:
                env_sharedflows.remove(sharedflow["name"])


    # --- API PRODUCTS ---
    # Algorithm
    # Before iteration clean apiproducts from non existing proxies.
    # 1. Check if api product has any attached proxy to it
    #   a. If true then we skip this product
    # 2. Iterate though the list of apps that attached to this product
    # 3. Remove dependency from the apps and current api product
    # 4. Remove api product itself
    def delete_api_products(self):
        self.log("--- Processing API PRODUCTS ---")
        self.api_products_clean_up()

        apiproducts = self.hierarchy.get("apiproduct")
        for apip in apiproducts[:]:
            if len(apip["proxy"]) > 0:
                self.log(f"API product: {apip["name"]} has active proxies. Skipping.")
                continue
            
            apps_using = apip.get("app", [])
            for app_name in apps_using:
                self.detach_product_from_app(app_name, apip["name"])

            url = f"{self.main_url}/apiproducts/{apip["name"]}"
            if self.api_delete(url, f"API Product {apip["name"]}"):
                apiproducts.remove(apip)

    def detach_product_from_app(self, app_name, product_name):
        # Helper to find dev and remove key association
        app_obj = next((a for a in self.hierarchy["app"] if a["name"] == app_name), None)
        if not app_obj: return

        dev_email = app_obj["developer"]
        
        url = f"{self.main_url}/developers/{dev_email}/apps/{app_name}"
        app_details = self.request.get(url).json()

        self.log(f"Revoking/Removing product {product_name} from App {app_name} (Dev: {dev_email})")

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


    # -- DEVELOPERS AND APPS ---
    # 1. Check if developer has apps
    #   a. If false, the safely delete this developer
    # 2. Else iterate though developer's apps
    # 3. Match apps with existing apps
    # 4. If The app doesn't have any api product, then remove it from dev list and itself
    # 5. If developer was left with no apps, then remove the developer
    def delete_developer_and_apps(self):
        self.log("--- Processing DEVS & APPS ---")
        
        developers = self.hierarchy.get("developers", [])
        for dev in developers[:]:
            # Check if dev has any apps
            dev_apps = dev.get("app", [])
            for app_name in dev_apps[:]:
                full_app = next((a for a in self.hierarchy["app"] if a["name"] == app_name), None)

                if full_app and len(full_app["apiproduct"]) < 1:
                    self.log(f"Deleting App {app_name} (no products)")
                    url = f"{self.main_url}/developers/{dev['email']}/apps/{app_name}"
                    if self.api_delete(url, f"App {app_name}"):
                        dev_apps.remove(app_name)
                        if full_app in self.hierarchy["app"]:
                            self.hierarchy["app"].remove(full_app)

                if len(dev_apps) < 1:
                    url = f"{self.main_url}/developers/{dev["email"]}"
                    if self.api_delete(url, f"Developer {dev["email"]}"):
                        developers.remove(dev)

    # --- KEY VALUE MAPS ---
    # Algorithm
    # 1. According to left proxies, get all the kvm that they use
    # 2. Iterate though org_kvm and remove kvms that are not in the safe list
    # 3. Iterate though env_kvm and remove kvms that are not in the safe list
    def delete_kvms(self):
        self.log("--- Processing KVMs ---")
        safe_kvms = self.find_kvms_used_in_proxies_and_sharedflows()

        # Org kvms
        org_kvm = self.hierarchy["organization_kvm"]
        for kvm in org_kvm[:]:
            if kvm not in safe_kvms:
                url = f"{self.main_url}/keyvaluemaps/{kvm}"
                if self.api_delete(url, f"Org KVM {kvm}"):
                    org_kvm.remove(kvm)

        # Env kvms
        envs = self.hierarchy["environments"]
        for env in envs:
            env_kvm = env["kvm"]
            for kvm in env_kvm[:]:
                if kvm not in safe_kvms:
                    url = f"{self.main_url}/environments/{env['name']}/keyvaluemaps/{kvm}"
                    if self.api_delete(url, f"Env KVM {kvm} in {env["name"]}"):
                        env_kvm.remove(kvm)

    def find_kvms_used_in_proxies_and_sharedflows(self):
        used_kvms = set()
        proxies = self.hierarchy["proxy"]
        
        self.log(f"Starting static analysis of {len(proxies)} proxies...")
        for proxy in proxies:
            proxy_name = proxy["name"]
            
            revisions = proxy["revisions"]
            for revision in list(revisions.keys()):
                self.log(f"Checking {proxy_name} revision {revision}...")
                url = f"{self.main_url}/apis/{proxy["name"]}/revisions/{revision}?format=bundle"
                zip_folder_prefix = "apiproxy/policies/"

                self.scan_bundle_for_kvm(url, zip_folder_prefix, used_kvms, f"Proxy {proxy_name}")

        sharedflows = self.hierarchy.get("sharedflow", [])
        self.log(f"Starting static analysis of {len(sharedflows)} sharedflows...")

        for sf in sharedflows:
            sf_name = sf["name"]            
            revisions = sf.get("revisions", {})
            
            for revision in list(revisions.keys()):
                self.log(f"Checking SharedFlow {sf_name} revision {revision}...")
                url = f"{self.main_url}/sharedflows/{sf_name}/revisions/{revision}?format=bundle"
                zip_folder_prefix = "sharedflowbundle/policies/"
                
                self.scan_bundle_for_kvm(url, zip_folder_prefix, used_kvms, f"SharedFlow {sf_name}")

        self.log(f"Found {len(used_kvms)} unique KVMs used in code: {used_kvms}")
        return used_kvms
    
    def scan_bundle_for_kvm(self, url, folder_prefix, used_kvms_set, context_name):
        try:
            response = self.request.get(url)
            response.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                for filename in z.namelist():
                    if filename.startswith(folder_prefix) and filename.endswith(".xml"):
                        with z.open(filename) as policy_file:
                            try:
                                self.parse_policy_for_kvm(policy_file, used_kvms_set)
                            except ET.ParseError:
                                self.log(f"Error parsing XML in {context_name}: {filename}")
        
        except requests.exceptions.RequestException as e:
            self.log(f"Failed to download bundle for {context_name}: {e}")
        except zipfile.BadZipFile:
            self.log(f"Invalid ZIP file received for {context_name}")

    def parse_policy_for_kvm(self, policy_file, used_kvms_set):
        try:
            tree = ET.parse(policy_file)
            root = tree.getroot()

            if root.tag == "KeyValueMapOperations":
                kvm_name = None
                
                if "mapIdentifier" in root.attrib:
                    kvm_name = root.attrib["mapIdentifier"]
                else:
                    map_name_element = root.find("MapName")
                    if map_name_element is not None:
                        kvm_name = map_name_element.text

                if kvm_name:
                    used_kvms_set.add(kvm_name)
                    
        except Exception as e:
            pass

    # --- ENVIRONMENTS ---
    # Algorithm
    # 1. Check if env has any proxies
    # 2. Check if env has any sharedFlows
    # 3. Check for kvms
    # 4. If env is blank then delete it
    # ------------------------ 
    def delete_environments(self):
        self.log("--- Processing ENVIRONMENTS ---")
        
        envs = self.hierarchy["environments"]
        for env in envs[:]:
            # Check if env has any proxies or sharedflows
            has_proxies = len(env["proxy"]) > 0
            has_sharedflows = len(env["sharedflow"]) > 0 
            if has_proxies or has_sharedflows:
                self.log(f"Skipping Env {env["name"]}: not empty.")
                continue
            
            self.detach_from_instances(env["name"])

            url = f"{self.main_url}/environments/{env["name"]}"
            if self.api_delete(url, f"Environment {env["name"]}"):
                envs.remove(env)
    
    def detach_from_instances(self, env_name):
        base_url = f"{self.main_url}/instances"
        response = self.request.get(base_url)
        instances = response.json().get("instances", [])

        for instance in instances:
            inst_name = instance["name"]
            url = f"{base_url}/{inst_name}/attachments"
            response = self.request.get(url)

            attachments = response.json().get("attachments", [])

            attachment_obj = next((a for a in attachments if a["environment"] == env_name), None)
            if attachment_obj:
                url = f"{base_url}/{inst_name}/attachments/{attachment_obj["name"]}"
                self.api_delete(url, f"Attachment env: {env_name} to instance: {inst_name}")
                self.wait_for_env_detach(env_name, inst_name)

    def wait_for_env_detach(self, env_name, instance_name, timeout=300):
        start_time = time.time()
        self.log(f"Waiting for environment '{env_name}' to detach from instance '{instance_name}'...")

        url = f"{self.main_url}/instances/{instance_name}/attachments"

        while time.time() - start_time < timeout:
            try:
                response = self.request.get(url)

                if response.status_code == 200:
                    attachments = response.json().get("attachments", [])

                    is_still_attached = any(att.get("environment") == env_name for att in attachments)
                    if not is_still_attached:
                        self.log(f"Environment '{env_name}' detached successfully.")
                        return True
                else:
                    self.log(f"Unexpected status checking attachments: {response.status_code}")

            except Exception as e:
                self.log(f"Error checking attachment: {e}")
            
            time.sleep(5)
        
        self.log(f"Timeout waiting for env detach: {env_name}")
        return False

    def clean(self):
        self.delete_proxies()
        self.delete_sharedflows()
        self.delete_api_products()
        self.delete_developer_and_apps()
        self.delete_kvms()
        self.delete_environments()

        # TO-DO: portals, custom reports, instances, data collectors, env-group cleanup

        with open("cleaner_output.json", "w") as file:
            json.dump(self.hierarchy, file, indent=4)

        