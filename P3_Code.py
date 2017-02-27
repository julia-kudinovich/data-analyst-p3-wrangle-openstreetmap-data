
# coding: utf-8

# In[63]:

import csv
import codecs
import xml.etree.cElementTree as ET
from collections import defaultdict
import re
import pprint
import sqlite3
import cerberus
import sch


# In[64]:

osm_file = "las-vegas_nevada.osm"
lower = re.compile(r'^([a-z]|_)*$')
lower_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')
problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

#Function 'process_map' below will show counts of different tag types in the data
def key_type(element, keys):
    if element.tag == "tag":
        if lower.search(element.attrib['k']):
            keys["lower"]+=1
        elif lower_colon.search(element.attrib['k']):
            keys["lower_colon"]+=1
        elif problemchars.search(element.attrib['k']):
            keys["problemchars"]+=1
        else:
            keys["other"]+=1
        pass
    return keys

def process_map(filename):
    keys = {"lower": 0, "lower_colon": 0, "problemchars": 0, "other": 0}
    for _, element in ET.iterparse(filename):
        keys = key_type(element, keys)

    return keys

keys = process_map(osm_file)
pprint.pprint(keys)


# In[65]:

street_type_re = re.compile(r'\b\S+\.?$',re.IGNORECASE)
expected = ["Street", "Avenue", "Boulevard", "Drive", "Court", "Place", "Square", "Lane", "Road",
            "Trail", "Parkway", "Commons", "Circle", "Way"]

#The function 'audit 'below will check if the street type is expected (i.e belongs to expected list). 
#If not it will output 'unexpected' street names

def audit_street_type(street_types, street_name):
    m = street_type_re.search(street_name)
    if m:
        street_type = m.group()
        if street_type not in expected:
            street_types[street_type].add(street_name)

def is_street_name(elem):
    return (elem.attrib['k'] == "addr:street")

def audit(osm_file):
    street_types = defaultdict(set)
    for event, elem in ET.iterparse(osm_file, events=("start",)):
        if elem.tag == "node" or elem.tag == "way":
               for tag in elem.iter("tag"):
                if is_street_name(tag):
                    audit_street_type(street_types, tag.attrib['v'])
    return street_types

st_types = audit(osm_file)
pprint.pprint(dict(st_types))


# In[66]:

#Audit zip codes. All Las Vegas zip codes must start with '89'
def is_postcode(elem):
    return (elem.attrib['k'] == "addr:postcode")

def audit_zip(osm_file):
    invalid_zip =[]
    for event, elem in ET.iterparse(osm_file, events=("start",)):
        if elem.tag == "node" or elem.tag == "way":
               for tag in elem.iter("tag"):
                if is_postcode(tag):
                    #Checking if zip starts with 89
                    if not tag.attrib['v'].startswith("89"):
                        invalid_zip.append(tag.attrib['v']) 
    return invalid_zip

invalid_zip = audit_zip(osm_file)
print invalid_zip


# In[67]:

#Function to replace abbreviated street types with expected values.
mapping = { "St": "Street",
            "St.": "Street",
            "Ave": "Avenue",
            "AVE": "Avenue",
            "Ave.": "Avenue",
            "ave": "Avenue",
            "Blvd": "Boulevard",
            "Blvd.": "Boulevard",
           "blvd": "Boulevard",
           "blvd.": "Boulevard",
            "Rd": "Road",
            "Rd.": "Road",
           "Rd5": "Road",
            "Dr" : "Drive",
           "Dr." : "Drive",
           "Pkwy" : "Parkway",
           "Cir" : "Circle",
           "Ln" : "Lane",
           "Ln." : "Lane",
            "S": "South",
           "S.": "South",
            "N": "North",
           "N.": "North",
           "W": "West",
            "W.": "West",
           "E": "East",
           "E.": "East"
        }



def update_name(name, mapping):
    new_name = []
    for i in name.split(" "):
        if i in mapping.keys():
            i = mapping[i]
        new_name.append(i)
    return " ".join(new_name).replace(",","")

#Function to remove building/suite number form street address
bld_num = ["Suite", "Ste", "#", "STE"]

def remove_bld_num(name, mapping):
    for i in name.split(" "):
        if any(bld in i for bld in bld_num):
            return name.split(i)[0].strip()
    return name

#Function to fix zipcodes
def fix_zip(name):
    return name[-5:]


# In[69]:

OSM_PATH = "las-vegas_nevada.osm"

NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"

LOWER_COLON = re.compile(r'^([a-z]|_)+:([a-z]|_)+')
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

SCHEMA = sch.schema

# Make sure the fields order in the csvs matches the column order in the sql table schema
NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']

def get_tags(element):
    tags = []
    for i in element.iter("tag"):
        tag={}
        tag["id"] =  element.attrib["id"]
        tag_key = i.attrib['k']
        if PROBLEMCHARS.search(tag_key):
            continue
        elif ":" in tag_key:
            tag_pieces =  tag_key.split(':')
            tag["type"] = tag_pieces[0]
            if len(tag_pieces)==3:
                tag["key"] = tag_pieces[1]+":"+tag_pieces[2]
            else:
                tag["key"] = tag_pieces[1]
        else:
            tag["type"] = "regular"
            tag["key"] = tag_key
        
         
        if tag["key"]== "street":
            for key,value in st_types.iteritems():
                if i.attrib["v"] in value:
                    #Fix street type if it is in the `st_types` list we found before
                    tag["value"] = update_name(i.attrib["v"] , mapping)
                    #Remove building number from street address
                    tag["value"] = remove_bld_num(tag["value"], mapping)
        
        #Fix invaid postcodes
        if tag["key"] == "postcode":
            if not i.attrib['v'].startswith("89"):
                tag["value"] = fix_zip(i.attrib['v'])
    
        else:
            # Removing commas if any from the tag["value"] because when loading into sql database 
            #they are interpreted as column breaks
            tag["value"] = i.attrib["v"].replace(",","")
        tags.append(tag)
    return tags

def shape_element(element, node_attr_fields=NODE_FIELDS, way_attr_fields=WAY_FIELDS,
                  problem_chars=PROBLEMCHARS, default_tag_type='regular'):
    node_attribs = {}
    way_attribs = {}
    way_nodes = []
    tags = []  # Handle secondary tags the same way for both node and way elements

    if element.tag == 'node':
        node_attribs["id"] = element.attrib["id"]
        node_attribs["lat"] =  element.attrib['lat']
        node_attribs["lon"] =  element.attrib['lon']
        node_attribs["user"] =  element.attrib['user']
        node_attribs["uid"] =  element.attrib['uid']
        node_attribs["version"] =  element.attrib['version']
        node_attribs["changeset"] =  element.attrib['changeset']
        node_attribs["timestamp"] =  element.attrib['timestamp']
        
        tags = get_tags(element)
       
        return {'node': node_attribs, 'node_tags': tags}
        
    elif element.tag == 'way':
        way_attribs["id"] = element.attrib["id"]
        way_attribs["user"] =  element.attrib['user']
        way_attribs["uid"] =  element.attrib['uid']
        way_attribs["version"] =  element.attrib['version']
        way_attribs["changeset"] =  element.attrib['changeset']
        way_attribs["timestamp"] =  element.attrib['timestamp']
        
        tags = get_tags(element)
        
        nd_count=0
        for i in element.iter("nd"):
            nd={}
            nd["id"] =  element.attrib["id"]
            nd["node_id"] =  i.attrib["ref"]
            nd["position"] =  nd_count
            way_nodes.append(nd)
            nd_count+=1
        

        return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}
    
    
# ================================================== #
#               Helper Functions                     #
# ================================================== #
def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag"""

    context = ET.iterparse(osm_file, events=('start', 'end'))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()


def validate_element(element, validator, schema=SCHEMA):
    """Raise ValidationError if element does not match schema"""
    if validator.validate(element, schema) is not True:
        field, errors = next(validator.errors.iteritems())
        message_string = "\nElement of type '{0}' has the following errors:\n{1}"
        error_string = pprint.pformat(errors)
        
        raise Exception(message_string.format(field, error_string))


class UnicodeDictWriter(csv.DictWriter, object):
    """Extend csv.DictWriter to handle Unicode input"""

    def writerow(self, row):
        super(UnicodeDictWriter, self).writerow({
            k: (v.encode('utf-8') if isinstance(v, unicode) else v) for k, v in row.iteritems()
        })

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


# ================================================== #
#               Main Function                        #
# ================================================== #
def process_map(file_in, validate):
    """Iteratively process each XML element and write to csv(s)"""

    with codecs.open(NODES_PATH, 'w') as nodes_file,          codecs.open(NODE_TAGS_PATH, 'w') as nodes_tags_file,          codecs.open(WAYS_PATH, 'w') as ways_file,          codecs.open(WAY_NODES_PATH, 'w') as way_nodes_file,          codecs.open(WAY_TAGS_PATH, 'w') as way_tags_file:

        nodes_writer = UnicodeDictWriter(nodes_file, NODE_FIELDS)
        node_tags_writer = UnicodeDictWriter(nodes_tags_file, NODE_TAGS_FIELDS)
        ways_writer = UnicodeDictWriter(ways_file, WAY_FIELDS)
        way_nodes_writer = UnicodeDictWriter(way_nodes_file, WAY_NODES_FIELDS)
        way_tags_writer = UnicodeDictWriter(way_tags_file, WAY_TAGS_FIELDS)

        nodes_writer.writeheader()
        node_tags_writer.writeheader()
        ways_writer.writeheader()
        way_nodes_writer.writeheader()
        way_tags_writer.writeheader()

        validator = cerberus.Validator()

        for element in get_element(file_in, tags=('node', 'way')):
            el = shape_element(element)
            if el:
                #if validate is True:
                    #validate_element(el, validator)

                if element.tag == 'node':
                    nodes_writer.writerow(el['node'])
                    node_tags_writer.writerows(el['node_tags'])
                elif element.tag == 'way':
                    ways_writer.writerow(el['way'])
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])


if __name__ == '__main__':
    # Note: Validation is ~ 10X slower. For the project consider using a small
    # sample of the map when validating.
    process_map(OSM_PATH, validate=True)

