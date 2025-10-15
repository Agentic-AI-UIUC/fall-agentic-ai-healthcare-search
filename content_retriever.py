from selenium import webdriver
from selenium.webdriver.common.by import By
import time
from page_classifier import PageClassifier

def check_url(func):
    def wrapped(self,*args,**kwargs):
        if not len(self.current_url):
            print("URL empty")
            return ""
        return func(self,*args,**kwargs)
    return wrapped

class ContentRetriever:
    def __init__(self, base_url: str, text_classifer: PageClassifier = None):
        options = webdriver.FirefoxOptions()
        self.driver = webdriver.Firefox(options=options)

        self.text_classifier = text_classifer

        self.current_url = ""
        self.base_url = base_url

    @check_url
    def check_text(self, up_to: int = 20) -> bool:
        elems = self.driver.find_elements(value='''p''',by=By.TAG_NAME)

        text = ''''''
        for elem in elems[:min(up_to,len(elems))]:
            text += " " + elem.text

        return self.text_classifier.page_fits(text)
    
    # will only work for the MSD website (this should be customizable)
    def get_title(self) -> str:
        elems = self.driver.find_elements(value='''h1''',by=By.TAG_NAME)

        if not len(elems):return "No title found"

        text = elems[0].text

        return text

    @check_url
    def retrive_all_links_on_base(self) -> list:
        elems = self.driver.find_elements(value='''//a[@href]''',by=By.XPATH)

        to_return = set()
        for elem in elems:
            link = elem.get_attribute("href")
            if self.base_url in link:
                extension = link[len(self.base_url) + 1:]
                if "?" in extension:
                    extension = extension[:extension.index("?")]
                elif "#" in extension:
                    extension = extension[:extension.index("#")]
                to_return.add(extension)

        return list(to_return)
    
    @check_url
    def respond_to_cookie_request(self) -> None:
        elems = self.driver.find_elements(value='''onetrust-reject-all-handler''',by=By.ID)
        if not len(elems): return
        elem = elems[0]
        elem.click()

    @check_url
    def retrieve_all_relevant_information(self) -> str:
        #this is the basic function, but idk if i should add checks
        elems = self.driver.find_elements(value='''p''',by=By.TAG_NAME)

        text = ''''''
        for elem in elems:
            text += " " + elem.text

        return text
    
    def set_url(self,url: str) -> None:
        self.current_url = url
        self.driver.get(self.current_url)
        time.sleep(2)

    def kill_process(self) -> None:
        self.driver.quit()


if __name__ == "__main__":
    retriever = ContentRetriever()
    retriever.retrieve_check_text()