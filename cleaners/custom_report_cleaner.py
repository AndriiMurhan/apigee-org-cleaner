from .base_cleaner import BaseCleaner

class CustomReportCleaner(BaseCleaner):
    def __init__(self, hierarchy: object, main_url: str):
        super().__init__(hierarchy, main_url)

    def delete(self):
        self.delete_custom_reports()

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