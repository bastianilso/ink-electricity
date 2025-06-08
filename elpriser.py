#!/usr/bin/python
# -*- coding:utf-8 -*-
import json
import os
import locale
import requests
from requests.adapters import HTTPAdapter, Retry
from datetime import date, datetime
import calendar
from lxml import etree

# Setup Directories and input/output
screendir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'screen')
svg_template = 'screen_template.svg'
svg_screen = 'screen_current.svg'
image_screen = 'screen_current.png'

filename_template = 'screen_template'
filename_out = 'screen_current'
svg_template = os.path.join(screendir, filename_template + '.svg')
svg_out = os.path.join(screendir, filename_out + '.svg')
ns = {'s': 'http://www.w3.org/2000/svg'}

# Ensure consistent locale
sys_locale = locale.getlocale()
locale.setlocale(locale.LC_ALL, 'da_DK.UTF-8')

# Setup session
session = requests.Session()

# SVG namespace and tree
tree = etree.parse(open(svg_template))
ns = {'s': 'http://www.w3.org/2000/svg'}

def SetText(tree, identifier, value):
  root = tree.getroot()
  for elem in root.getiterator():
      try:
          elem.text = elem.text.replace(identifier, value)
      except AttributeError:
          pass

# ElUpdate updates the current electricity price and timestamp.
def ElUpdate():
    user_agent = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
    url ="https://elprisen.somjson.dk/elpris?GLN_Number=5790000611003"
    response = session.get(url, headers = user_agent)
        
    data = json.loads(response.text)
    
    # Noteworthy data:
    #hour0 = data['records'][0] - records is a list, in each index there are the following info:
    #hour0['HourDK'], '2024-02-23T00:00:00' - the hour of the price
    #hour0['CO2Emission'] - the CO emitted
    #hour0['SpotPrice'] - price, excluding tariffs
    #hour0['NetselskabTarif'] - price including tariffs
    #hour0['Total'] - total price
    
    # Set the current price and current time.
    now = datetime.now()
    current_time = now.strftime("%H") # H - hour, M- minute, S - second
    print("Current Time =", current_time)
    print("Current Price =", data['records'][int(current_time)]['Total'])
    pricenow = round(data['records'][int(current_time)]['Total'],2) 
    
    SetText(tree, "$nu", str(pricenow) + "kr.")
    SetText(tree, "$tidnu", datetime.now().strftime("%d/%m %H:%M"))

# ElBarChart alters the height of 33 bars in the svg file, according to the hour price.
# It is variable how far ahead we can look into the future.
def ElBarChart():
    user_agent = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
    url ="https://elprisen.somjson.dk/elpris?GLN_Number=5790000611003"
    response = session.get(url, headers = user_agent)
    data = json.loads(response.text)
    
    # Determine the hour of the first/last bar
    now = datetime.now()
    current_time = now.strftime("%H") # H - hour, M- minute, S - second
    num_bars = 33 # number of bars
    time_start = int(current_time)-12 # 06:00
    records_length = len(data['records'])
    time0 = int(datetime.strptime(data['records'][0]['HourDK'], '%Y-%m-%dT%H:%M:%S').strftime("%H"))
    first_bar = time_start - time0
    print("Proposed Time Start: " + str(time_start))
    print("Length of records: " + str(records_length))
    print("First Bar: " + str(first_bar))
    
#    if (time_start+num_bars > records_length):
#        print("Proposed Time Start " + str(time_start+num_bars) + " is longer than available records" + records_length)
#        time_start = max(records_length-num_bars,0)
#        print("New Proposed Time Start is " + str(time_start))
    
    # Prepare each bar and associated elements
    for i in range(0,num_bars):            
        offset = i+first_bar
        
        # In case we have more bars than available data, we create "empty" entries
        # that remain invisible in the final image.
        if (offset >= len(data['records'])):
            data['records'].insert(offset, {'HourDK': "", 'Total': 0.001})
            print("Empty bars inserted for hour: " + str(offset))
        if (data['records'][offset]['HourDK'] == ""):
            hour = ""
        else: 
            hour = datetime.strptime(data['records'][offset]['HourDK'], '%Y-%m-%dT%H:%M:%S').strftime("%H")
        
        # Insert text for each hour (e.g. $b0.)
        b_ns = "$b" + str(i) + "."  
        SetText(tree, b_ns, str(hour))

        # Remove vertical highlight lines everywhere except for the line that match the current timestamp.
        line_ns = "bl" + str(i)
        to_remove = tree.find('.//{http://www.w3.org/2000/svg}rect[@id="' + line_ns + '"]')        
        if to_remove is not None:
            if (hour != current_time):
                p = to_remove.getparent()
                p.remove(to_remove)

        # Calculate height of bar, based on its price
        price_max = 4 # the maximum y label on the chart.
        bar_max = 50 # the corresponding height of each bar at max label.
        price = data['records'][offset]['Total']
        convprice = bar_max * (price / price_max)
        bar_ns = "bar" + str(i)

        # Adjust each bar based on its ID.
        rect = tree.find('.//{http://www.w3.org/2000/svg}rect[@id="' + bar_ns + '"]')
        if rect is not None:
            rect.set('height', str(convprice))  # Set the new width

# Call each function
ElUpdate()
ElBarChart()

# Set locale back to system for export, to avoid converting ø to weird characters. 
locale.setlocale(locale.LC_ALL, 'C')

# Write changes to the svg file screen_current
with open(svg_out, "wb") as o:
    o.write(etree.tostring(tree, pretty_print=True))
    
# Call Inkscape to export the SVG as PNG.
os.system("inkscape -w 800 -h 480 " + os.path.join(screendir, filename_out + '.svg') + " --export-area-page --export-background-opacity=1 --export-filename " + os.path.join(screendir, filename_out + '.png'))

# Prepare a 1-bit flipped and rotated bitmap for ESP8266
os.system("convert " + os.path.join(screendir, filename_out + '.png') + " -flop -rotate 180 -threshold 55% -monochrome " + os.path.join(screendir, filename_out + '.bmp'))
