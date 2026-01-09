from .base_cleaner import BaseCleaner

class SharedflowCleaner(BaseCleaner):
    def __init__(self, hierarchy: object, main_url: str):
        super().__init__(hierarchy, main_url)

    def delete(self):
        self.delete_sharedflows()

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
                    self.api_helper.wait_for_undeploy(env_name, "sharedflows", sharedflow["name"], revision, self.main_url)  # -------------------- PROTECTION -----------------------

            # Check and delete all posible sharedFlow dependencies
            self.delete_shareflow_dependencies(sharedflow)

            self.logger.log(f"Deleting sharedflow {sharedflow["name"]}")
            url = f"{self.main_url}/sharedflows/{sharedflow['name']}"
            if self.api_helper.api_delete(url, f"SharedFlow {sharedflow["name"]}"):
                sharedflows.remove(sharedflow)

    def detach_flowhook(self, env_name: str, sf_name: str):
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