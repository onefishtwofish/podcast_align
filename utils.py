import yaml

def get_config(path="config.yaml"):
    with open("config.yaml") as stream:
        return yaml.safe_load(stream)
