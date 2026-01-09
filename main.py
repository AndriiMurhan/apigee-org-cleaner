import time

from extracter import ExtracterApigeeResources
from cleaner import ApigeeOrganizationCleaner
from CSVParser import CSVParser

if __name__ == "__main__":
   start = time.time()
   extracter = ExtracterApigeeResources(organization="sturdy-gate-482111-f9")
   print("Starting extraction...")
   data1 = extracter.build_hierarchy("hierarchy.json")

   # Temporary access to hierarchy.json
#    with open("hierarchy.json", "r") as jsonFile:
    #    data1 = json.load(jsonFile)

   parser = CSVParser()
   data2 = parser.parse("resources.txt")
   
   cleaner = ApigeeOrganizationCleaner(data2, data1, organization="sturdy-gate-482111-f9")
   cleaner.clean()
   
   end = time.time()
   print(f"Time to complete: {end-start}")