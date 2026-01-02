from request import RestRequest
import xml.etree.ElementTree as ET
import requests
import zipfile
import io
import json

class Cleaner():
    def __init__(self, filterList, hierarchy,
                 domain="apigee.googleapis.com", 
                 organization="gcp101027-apigeex"):
        self.filterList = filterList
        self.hierarchy = hierarchy
        self.domain = domain
        self.main_url = f"https://{self.domain}/v1/organizations/"
        self.organization = organization
        self.request = RestRequest()

    def allowedToDelete(self, proxy):
        return proxy not in self.filterList

    # Proxy
    # ------------------------
    # Algorithm
    # 1. Check if proxy is in the filter list
    #   a. If in the list then skip it
    # 2. Iterate though revisions and undeploy every revision from its enviroment
    # 3. When every revision is undeployed, remove proxy dependenies in the hierarchy and organization
    # 4. Remove proxy itself from hierarchy.json and organization (DELETE Request)
    def deleteProxies(self):
        proxies = self.hierarchy["proxy"]

        for proxy in proxies[:]:
            #  Check if proxy is in the filter list
            if not self.allowedToDelete(proxy["name"]):
                print(f"Proxy that are not allow to delete: {proxy}")
                continue
            
            # Iterate thought proxy revisions, undeploy it and remove from hierarchy
            # ---
            revisions = proxy["revisions"]
            for revision in revisions.keys():
                # request to undeploy
                # DELETE: organizations/{org}/environments/{env}/apis/{api}/revisions/{rev}
                None
            # ---
            
            # Check and delete all posible proxy dependencies
            self.deleteProxyDependencies(proxy["name"])

            # Delete proxy itself: DELETE request
            # DELETE: organizations/{org}/apis/{api}
            proxies.remove(proxy)

    def deleteProxyDependencies(self, proxy: object) -> None:
        # Enviroment dependency
        for env in self.hierarchy["environments"]:
            env_proxies = env["proxy"]
            while proxy in env_proxies:
                env_proxies.remove(proxy)

        # SharedFlow dependency
        for sh in self.hierarchy["sharedflow"]:
           sh_proxies = sh["proxy"]
           while proxy in sh_proxies:
               sh_proxies.remove(proxy)

        # API Products
        for apip in self.hierarchy["apiproduct"]:
            apip_proxies = apip["proxy"]
            while proxy in apip_proxies:
                apip_proxies.remove(proxy)
    # ------------------------


    # SharedFlow
    # Algorithm
    # 1. Check if any not deleted proxy has attached the proxy to it
    #   a. If has than we skip it
    # 2. Check if the sharedflow is attached to any flowhook in valid enviroments
    #   b. If it is then iterate thought env list and detach from it
    # 3. Undeploy sharedflow from enviremont
    # 4. Remove all possible dependencies with other resources
    # 5. Remove sharedFlow itself.
    # ------------------------
    def deleteSharedFlows(self):
        sharedFlows = self.hierarchy["sharedflow"]

        for sharedFlow in sharedFlows[:]:
            # Check if shared flow is attached to any proxy
            if len(sharedFlow["proxy"]) > 0:
                print(f"SharedFlow with name: {sharedFlow["name"]} is attached to proxy. Can't be removed!")
                continue
            
            # Check if shared flow is attached to any flowhook in enviroment
            envsWithAttachedSharedFlows = self.checkSharedFlowAttachedToFlowHook(sharedFlow)

            # If such sharedflows exist we will detach them and undeploy from this enviremonets
            for envWithAttachedSharedFlow in envsWithAttachedSharedFlows:
                # detaching and undeploying with DELETE Request
                # DELETE: organizations/{org}/environments/{env}/flowhooks/{flowhook}
                None

            # Undeploying
            for sh_revisions in sharedFlow["revisions"]:
                # DELETE request to undeploy
                # DELETE: organizations/{org}/environments/{env}/sharedflows/{sharedflow}/revisions/{rev}
                None

            # Check and delete all posible sharedFlow dependencies
            self.deleteSharedflowDependencies(sharedFlow)

            # Delete sharedflow itself: DELETE request
            # DELETE: organizations/{organizationId}/sharedflows/{sharedFlowId}
            sharedFlows.remove(sharedFlow)

    def checkSharedFlowAttachedToFlowHook(self, sharedflow: str) -> list:
        envsWithSharedFlow = []

        isAttached = False
        for env in self.hierarchy["environments"]:
            env_flowhooks = env["flowhook"]
            # Check attachment to flowhook in enviroment
            for flowhook in env_flowhooks:
                if flowhook["sharedflow"] == sharedflow["name"]:     
                    isAttached = True   
                    break

            if not isAttached:
                continue

            # Check if env is invalid(doesnt include any proxies) that means having sharedFlow in flowHook is usless
            if len(env["proxy"]) < 1:
                envsWithSharedFlow.append(env["name"])
        
        return envsWithSharedFlow

    def deleteSharedflowDependencies(self, sharedflow: object):
        # Enviroment dependency
        for env in self.hierarchy["environments"]:
            env_sharedflows = env["sharedflow"]
            if sharedflow["name"] in env_sharedflows:
                env_sharedflows.remove(sharedflow["name"])

    # ------------------------


    # API Products
    # Algorithm
    # Before iteration clean apiproducts from non existing proxies.
    # 1. Check if api product has any attached proxy to it
    #   a. If true then we skip this product
    # 2. Iterate though the list of apps that attached to this product
    # 3. Remove dependency from the apps and current api product
    # 4. Remove api product itself
    # ------------------------
    def deleteApiProducts(self):
        self.apiProductsCleanUp()
        apiproducts = self.hierarchy["apiproduct"]

        for apip in apiproducts[:]:
            # Check if api product has any proxies
            if len(apip["proxy"]) > 0:
                continue # We cant remove that important product

            # Check if api product has any attached app
            if "app" in apip:
                apps = apip["app"]

                for app in self.hierarchy["app"]:
                    if app["name"] in apps:
                        if(apip["name"] in app["apiproduct"]):
                            app["apiproduct"].remove(apip["name"])
                            apip["app"].remove(app["name"])
                    # Detach this app: DELETE Request
                    # DELETE: organizations/{org}/developers/{developerEmail}/apps/{app}/keys/{key}/apiproducts/{apiproduct}
                    # TO-DO: Multiple Credentials case
                None

            # DELETE: organizations/{org}/apiproducts/{apiproduct}
            apiproducts.remove(apip)

    def apiProductsCleanUp(self):
        apiproducts = self.hierarchy["apiproduct"]
        for apip in apiproducts:
            apip_proxies = apip["proxy"]
            for apip_proxy in apip_proxies[:]:
                is_exist = False
                for proxy in self.hierarchy["proxy"]:
                    if apip_proxy == proxy["name"]:
                        is_exist = True
                        break
                
                if not is_exist:
                    apip_proxies.remove(apip_proxy)
    # ------------------------

    # Developers and Apps
    # 1. Check if developer has apps
    #   a. If false, the safely delete this developer
    # 2. Else iterate though developer's apps
    # 3. Match apps with existing apps
    # 4. If The app doesn't have any api product, then remove it from dev list and itself
    # 5. If developer was left with no apps, then remove the developer
    # ------------------------
    def deleteDevelopersAndApps(self):
        developers = self.hierarchy["developers"]

        for dev in developers[:]:
            # Check if dev has any apps
            dev_apps = dev["app"]
            if len(dev_apps) < 1:
                # Delete the dev: DELETE request
                # DELETE: organizations/{org}/developers/{developerEmail}
                developers.remove(dev)
            else:
                # Iterate though the apps
                for dev_app in dev_apps[:]:
                    apps = self.hierarchy["app"]
                    # Find the app and check if it is still valid
                    for app in apps[:]:
                        if dev_app == app["name"] and dev["email"] == app["developer"]:
                            if len(app["apiproduct"]) < 1:
                                print(f"Dev: {dev["email"]}, app: {app["name"]}")
                                if app["name"] in dev_apps:
                                    dev_apps.remove(app["name"])
                                apps.remove(app)
                                # Remove App: Delete REQUEST
                                # DELETE: organizations/{org}/developers/{developerEmail}/apps/{app}

                if len(dev_apps) < 1:
                    # Remove dev: DELETE Request
                    # DELETE: organizations/{org}/developers/{developerEmail}
                    developers.remove(dev)
    # ------------------------

    # Key Value Maps
    # Algorithm
    # 1. According to led proxies, get all the kvm that they use
    # 2. Iterate though org_kvm and remove kvms that are not in the safe list
    # 3. Iterate though env_kvm and remove kvms that are not in the safe list
    # ------------------------
    def deleteKVMs(self):
        safe_kvms = self.find_kvms_used_in_proxies()
        print(safe_kvms)

        # Iterate though organizations kvms
        org_kvm = self.hierarchy["organization_kvm"]
        for kvm in org_kvm[:]:
            # Check the kvm
            if kvm not in safe_kvms:
                # DELETE request
                # DELETE: organizations/{org}/keyvaluemaps/{keyvaluemap}
                org_kvm.remove(kvm)

        # Iterate though enviroments kvms
        envs = self.hierarchy["environments"]
        for env in envs:
            env_kvm = env["kvm"]

            for kvm in env_kvm[:]:
                # Check the kvm
                if kvm not in safe_kvms:
                    # DELETE request
                    # DELETE: organizations/{org}/environments/{env}/keyvaluemaps/{keyvaluemap}
                    env_kvm.remove(kvm)

    def find_kvms_used_in_proxies(self):
        used_kvms = set()
        
        # Get all left proxies
        proxies = self.hierarchy["proxy"]
        
        print(f"Starting static analysis of {len(proxies)} proxies...")

        for proxy in proxies:
            proxy_name = proxy["name"]
            revisions = proxy["revisions"]

            for revision in list(revisions.keys()):
                print(f"  Checking {proxy_name} revision {revision}...")
                
                url = f"{self.main_url}{self.organization}/apis/{proxy["name"]}/revisions/{revision}?format=bundle"
                
                try:
                    response = self.request.get(url)
                    response.raise_for_status()

                    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                        for filename in z.namelist():
                            if filename.startswith("apiproxy/policies/") and filename.endswith(".xml"):
                                with z.open(filename) as policy_file:
                                    try:
                                        self.parse_policy_for_kvm(policy_file, used_kvms)
                                    except ET.ParseError:
                                        print(f"Error parsing XML: {filename}")
                except requests.exceptions.RequestException as e:
                    print(f"Failed to download bundle for {proxy_name} rev {revision}: {e}")

        print(f"Found {len(used_kvms)} used KVMs: {used_kvms}")
        return used_kvms
    
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
    # ------------------------

    # Environments
    # Algorithm
    # 1. Check if env has any proxies
    # 2. Check if env has any sharedFlows
    # 3. Check for kvms
    # 4. If env is blank then delete it
    # ------------------------ 
    def delete_environments(self):
        envs = self.hierarchy["environments"]

        for env in envs[:]:
            # Check if env has any proxies 
            if len(env["proxy"]) > 0:
                continue

            # Check if env has any sharedflows 
            if len(env["sharedflow"]) > 0:
                continue

            # Check if env has any kvms
            if len(env["kvm"]) > 0:
                continue

            # DELETE env REQUEST
            # DELETE: organizations/{org}/environments/{env}
            envs.remove(env)
        
    # ------------------------

    def clean(self):
        self.deleteProxies()
        self.deleteSharedFlows()
        self.deleteApiProducts()
        self.deleteDevelopersAndApps()
        self.deleteKVMs()
        self.delete_environments()

        with open("cleaner_output.json", "w") as file:
            json.dump(self.hierarchy, file, indent=4)
        