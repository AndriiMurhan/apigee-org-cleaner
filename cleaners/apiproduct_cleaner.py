from .base_cleaner import BaseCleaner

class APIProductCleaner(BaseCleaner):
    def __init__(self, hierarchy: object, main_url: str):
        super().__init__(hierarchy, main_url)

    def delete(self):
        self.delete_api_products()

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

    def detach_product_from_app(self, app_name: str, product_name: str):
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