import csv

# TO-DO: Improve parsing technology

class CSVParser:
    def parse(self, path):
        with open(path, mode ='r', newline='') as file:
            csvreader = csv.reader(file, delimiter=",")
            data = []
            for row in csvreader:
                for item in row:
                    data.append(item.strip())
        return data