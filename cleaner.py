import json
from utils.logger import Logger

from cleaners.proxy_cleaner import ProxyCleaner
from cleaners.sharedflow_cleaner import SharedflowCleaner
from cleaners.apiproduct_cleaner import APIProductCleaner
from cleaners.dev_and_app_cleaner import DevAndAppCleaner
from cleaners.kvm_cleaner import KVMCleaner
from cleaners.env_cleaner import EnvironmentCleaner
from cleaners.custom_report_cleaner import CustomReportCleaner
from cleaners.data_collector_cleaner import DataCollectorCleaner
from cleaners.envgroup_cleaner import EnvGroupCleaner
from cleaners.instance_cleaner import InstanceCleaner

class ApigeeOrganizationCleaner():
    def __init__(self, imp_proxies: list, hierarchy: object, domain: str = "apigee.googleapis.com", 
                 organization: str = "gcp101027-apigeex"):
        self.hierarchy = hierarchy
        self.domain = domain
        self.organization = organization
        self.main_url = f"https://{self.domain}/v1/organizations/{organization}"
        self.imp_proxies = imp_proxies
        self.logger = Logger(__class__.__name__)
        
        self.logger.log("--- INITIALIZING THE CLEANERS... ---")
        self.cleaners = [
            ProxyCleaner(self.imp_proxies, self.hierarchy, self.main_url),
            SharedflowCleaner(self.hierarchy, self.main_url),
            APIProductCleaner(self.hierarchy, self.main_url),
            DevAndAppCleaner(self.hierarchy, self.main_url),
            KVMCleaner(self.hierarchy, self.main_url),
            EnvironmentCleaner(self.hierarchy, self.main_url, self.domain),
            CustomReportCleaner(self.hierarchy, self.main_url),
            DataCollectorCleaner(self.hierarchy, self.main_url),
            EnvGroupCleaner(self.hierarchy, self.main_url)
            # InstanceCleaner(self.hierarchy, self.main_url)
        ]
    
    def clean(self):
        for cleaner in self.cleaners:
            cleaner.delete()

        self.logger.log("--- ORGANIZATIONS CLEANUP COMPLETED ---")

        with open("cleaner_output.json", "w") as file:
            json.dump(self.hierarchy, file, indent=4)

        