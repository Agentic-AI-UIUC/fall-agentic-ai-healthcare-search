import json, csv
import os
from page_classifier import PageClassifier
from content_retriever import ContentRetriever


class Scraper:
    def __init__(
        self,
        base_url: str,
        output_dir: str = "",
        first_url: str = "",
        save_every: int = 50,
        source: str = "unspecified",
        content_tags: str = "p",
        title_tags: str = "h1",
        cookie_close_id: str = "onetrust-reject-all-handler",
        page_sort: str = [
            "related to mental disorders",
            "unrelated to mental disorders",
        ],
    ):
        self.to_visit = set()
        self.to_visit.add(first_url if first_url else base_url)
        self.visited = []

        self.save_every = save_every
        self.base_url = base_url
        self.base_website = source
        self.output_dir = (
            output_dir if output_dir else os.path.dirname(os.path.abspath(__file__))
        )

        self.stop = False

        self.page_classifier = PageClassifier(page_sort)
        self.content_retriever = ContentRetriever(
            base_url=self.base_url,
            text_classifer=self.page_classifier,
            content_tags=content_tags,
            title_tags=title_tags,
            cookie_close_id=cookie_close_id,
        )

        self.template = {"to_visit": [], "visited": []}

    def initialize_save_state(self) -> None:
        json_path = os.path.join(self.output_dir, "save_state.json")
        json_read_type = "r+" if os.path.exists(json_path) else "w"

        with open(json_path, json_read_type) as file:
            x = json.load(file) if json_read_type == "r+" else dict()
            if not x.get("websites", 0):
                x["websites"] = dict()
            if not x["websites"].get(self.base_url, 0):
                x["websites"][self.base_url] = self.template
            else:
                self.to_visit = set(x["websites"][self.base_url]["to_visit"])
                self.visited = x["websites"][self.base_url]["visited"]
            file.seek(0)
            file.truncate()
            file.write(json.dumps(x, indent=2))

        csv_path = os.path.join(self.output_dir, "data.csv")
        csv_read_type = "r+" if os.path.exists(csv_path) else "w"

        with open(csv_path, csv_read_type) as file:
            try:
                reader = csv.reader(file)
                next(reader)
            except:
                writer = csv.writer(file)
                writer.writerow(["Title", "Source", "URL", "Content"])

    def mainloop(self) -> None:
        self.initialize_save_state()
        print("Starting web scraping!")

        if not len(self.to_visit):
            print("Nothing to scrape, exiting instead")

        counter = 0
        while len(self.to_visit):
            if self.stop:
                break
            counter += 1
            if counter > self.save_every:
                self.save_json_state()
                counter = 0
            url_args = self.to_visit.pop()
            if self.check_visited(url_args):
                continue

            url = f"{self.base_url}/{url_args}"
            try:
                self.content_retriever.set_url(url)

                print("Checking for cookies")
                self.content_retriever.respond_to_cookie_request()
                if not self.content_retriever.check_text():
                    continue
                print(f"Scraping {url}")

                print("Getting links")
                new_links = self.content_retriever.retrive_all_links_on_base()
                self.to_visit = self.to_visit.union(new_links)

                print("Retrieving text and title")
                content = self.content_retriever.retrieve_all_relevant_information()
                title = self.content_retriever.get_title()

                row = [title, self.base_website, url, content]

                print("Writing to csv")
                self.append_to_csv(row)
            except Exception as e:
                print(f"Exception occured: {e} with url {url}")
                break

        self.exit_operations()

    def set_stop(self):
        self.stop = True

    def check_visited(self, url: str) -> bool:
        if url in self.visited:
            return True
        self.visited.append(url)
        return False

    def append_to_csv(self, row) -> None:
        if not len(row):
            print("Nothing to write")
            return

        with open("data.csv", "a") as file:
            writer = csv.writer(file)
            if type(row[0]) == list:
                writer.writerows(row)
            else:
                writer.writerow(row)

    def save_json_state(self) -> None:
        json_path = os.path.join(self.output_dir, "save_state.json")
        with open(json_path, "r+") as file:
            old_json = json.load(file)

            to_visit_data = old_json.get("to_visit", []) + list(self.to_visit)
            visited_data = old_json.get("visited", []) + self.visited

            old_json["websites"][self.base_url]["to_visit"] = to_visit_data
            old_json["websites"][self.base_url]["visited"] = visited_data

            file.seek(0)
            file.truncate()
            file.write(json.dumps(old_json, indent=2))

    def exit_operations(self) -> None:
        print("Exiting Operations")

        self.save_json_state()

        self.content_retriever.kill_process()
