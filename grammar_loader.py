from textx import metamodel_from_file

def get_metamodel():
    return metamodel_from_file("testdatagen\\grammar\\testdatagen.tx")

def load_model_from_str(model_str):
    mm = get_metamodel()
    return mm.model_from_str(model_str)