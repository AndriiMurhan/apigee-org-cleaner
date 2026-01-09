import zipfile
import io
import xml.etree.ElementTree as ET
import requests

from request import RestRequest
from utils.logger import Logger

class BundleAnalyzer:
    def __init__(self):
        self.request = RestRequest()
        self.logger = Logger(__class__.__name__)


    def scan_bundle_for_resources(self, url: str, folder_prefix: str, 
                                  parser_callback, list_callback: set,
                                  context_name: str) -> set:        
        try:
            response = self.request.get(url)
            response.raise_for_status()
            
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                for filename in z.namelist():
                    if filename.startswith(folder_prefix) and filename.endswith(".xml"):
                        with z.open(filename) as policy_file:
                            try:
                                parser_callback(policy_file, list_callback)
                            except ET.ParseError:
                                self.logger.log(f"Error parsing XML in {context_name}: {filename}")
        
        except requests.exceptions.RequestException as e:
            self.logger.log(f"Failed to download bundle for {context_name}: {e}")
        except zipfile.BadZipFile:
            self.logger.log(f"Invalid ZIP file received for {context_name}")
        
        return list_callback
    
    def parse_policy_for_kvm(self, policy_file: str, used_kvms_set: set):
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
            self.logger.log(f"Error parsing KVM policy: {e}")
    
    def parse_policy_for_datacollector(self, policy_file: str, used_dcs_set: set):
        try:
            tree = ET.parse(policy_file)
            root = tree.getroot()
            
            if root.tag == "DataCapture":
                for capture in root.findall("Capture"):
                    dc_elem = capture.find("DataCollector")
                    
                    if dc_elem is not None and dc_elem.text:
                        dc_name = dc_elem.text.strip()
                        if dc_name:
                            used_dcs_set.add(dc_name)
        except Exception as e:
            self.logger.log(f"Error parsing DataCollector policy: {e}")