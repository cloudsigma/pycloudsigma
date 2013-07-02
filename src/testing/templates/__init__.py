__author__ = 'islavov'
import os

def get_template(template_name):
    with open(os.path.join(os.path.dirname(__file__), template_name), 'r') as tpl:
        return tpl.read()
