from pprint import pprint
import json

class Cleaner():
    def __init__(self, filterList, hierarchy):
        self.filterList = filterList
        self.hierarchy = hierarchy

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
                # GET request to undeploy
                None
            # ---
            
            # Check and delete all posible proxy dependencies
            self.deleteProxyDependencies(proxy["name"])

            # Delete proxy itself: DELETE request
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
                # detaching and undeploying with GET Request
                None

            # Undeploying
            for sh_revisions in sharedFlow["revisions"]:
                # GET request to undeploy
                None

            # Check and delete all posible sharedFlow dependencies
            self.deleteSharedflowDependencies(sharedFlow)

            # Delete sharedflow itself: DELETE request
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
                    # Detach this app: GET Request
                    # TO-DO: Multiple Credentials case
                None

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
                if len(dev_apps) < 1:
                    # Remove dev: DELETE Request
                    developers.remove(dev)


    def clean(self):
        self.deleteProxies()
        self.deleteSharedFlows()
        self.deleteApiProducts()
        self.deleteDevelopersAndApps()
        pprint(self.hierarchy)
        with open("cleaner_output.json", "w") as file:
            json.dump(self.hierarchy, file, indent=4)
        