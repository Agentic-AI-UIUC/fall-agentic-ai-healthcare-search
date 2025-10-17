from transformers import pipeline


class PageClassifier:
    def __init__(
        self, labels: list, positive_index: int = 0, threshold: float = 0.85
    ) -> None:
        self.classifier = pipeline(
            "zero-shot-classification", model="facebook/bart-large-mnli"
        )
        self.candidate_labels = labels
        self.positive_index = positive_index
        self.threshold = threshold

    def page_fits(self, text: str) -> bool:
        result = self.classifier(text, self.candidate_labels)

        max_in_list = max(result["scores"])
        max_index = result["scores"].index(max_in_list)

        return self.positive_index == max_index and max_in_list > self.threshold


if __name__ == "__main__":
    classifier = PageClassifier(
        ["related to mental illness", "unrelated to mental illness"]
    )
    with open("textfile.txt", "r") as file:
        text = file.read()
        print(classifier.page_fits(text))
