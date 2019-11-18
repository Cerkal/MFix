#!/usr/bin/env python3
import requests
import fileinput
import json
import glob
import os
import sys
import re

results = {
	"success" : [],
	"skipped" : []
}

options = {
	"h" : {
		'status' : False,
		'description': "print this help message and exit (also --help)"
	},
	"i" : {
		'status' : False,
		'description': "interactive prompt on before replacing found modules"
	},
	"s" : {
		'status' : False,
		'description': "silent mode (don't output anything)"
	},
	"u" : {
		'status' : False,
		'description': "pass url (-u <url>) runs only if the passed url returns a 500 response"
	},
	"V" : {
		'status' : False,
		'description': "print the version number and exit (also --version)"
	},
	"v" : {
		'status' : False,
		'description': "verbose (trace searched module.xml paths)"
	}
}

rows, columns = os.popen('stty size', 'r').read().split()
columns = int(columns)

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_screen(*args, **kwargs):
	if options["s"]["status"] == False:
		print(*args, **kwargs)


def print_version():
	print_screen("\nMFix 1.0, Searches and fixes out of date modules")
	print_screen("Author: John Cook - john.cook@kissusa.com")


def print_options():
	print_screen()
	print_screen("Options and arguments:")
	for option in options:
		print_screen("-" + option + "   : " + options[option]['description'])


def print_useage():
	print_version()
	print_screen()
	print_screen("usage: ./mfix.py [options] <path to magento root>")
	print_options()


def print_error(error):
	print_useage()
	print_screen(bcolors.FAIL)
	print_screen("[ ERROR: " + error + " ]")
	print_screen(bcolors.ENDC)
	sys.exit(1)


# Check for arguments 
if len(sys.argv) == 1:
	print_useage()
	sys.exit(1)


def url_validation(url):
	regex = re.compile(
        r'^(?:http|ftp)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
        r'localhost|' #localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
        r'(?::\d+)?' # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
	return re.match(regex, url) is not None


def parse_arguments():
	for option in sys.argv:
		if option == '--version':
			print_version()
			exit(0)
		if option == '--help':
			print_useage()
			exit(0)
		if option.startswith("-"):
			for x in option[1:len(option)]:
				if x in options:
					options[x]['status'] = True
				else:
					error = "Unknown argument %s" % option
					print_error(error)


parse_arguments()

if options["V"]["status"]:
	print_version()
	exit(0)

if options["h"]['status']:
	print_useage()
	exit(0)

if options["u"]['status']:
	# Check valid url
	url = sys.argv[len(sys.argv)-2]
	if url_validation(url):
		print_screen()
		print_screen("Checking url status...")
		try:
			status_code = requests.get(url).status_code
			print_screen("Status was %s for %s" % (status_code, url))
			if status_code == 200:
				print_screen("Nothing to do. Exiting.")
				exit(0)
		except requests.exceptions.RequestException as e:
			print_screen(e)
			sys.exit(1)
	else:
		print_error("Please enter a valid URL when using -u option")

print_screen('Scanning...')

# Check valid root
if os.path.isdir(sys.argv[len(sys.argv)-1]) == False:
	error = 'Path %s not found, please enter a valid path' % sys.argv[len(sys.argv)-1]
	print_error(error)


MAGENTO_ROOT = sys.argv[len(sys.argv)-1]
modules_found = {}

# Check for error reported folder
if 'report' not in os.listdir(MAGENTO_ROOT+'/var'):
	print_screen('Report folder not found')
	exit(0)

# Check if not empty
if len(os.listdir(MAGENTO_ROOT+'/var/report')) == 0:
	print_screen('Report file not found')
	exit(0)


def get_error_file(path=MAGENTO_ROOT+'/var/report/*'):
	# Glob makes unix search pattens possible like: *
	report_dir = glob.glob(path)
	latest_file = max(report_dir, key=os.path.getctime)
	return latest_file


def line_is_valid_module_error(line):
	if 'defined in codebase' in line:
		return True
	return False


def create_dictonary(line):
	string = "<start>%s<end>" % line
	name = find_between(
		string, 
		"<start>", 
		" db"
	)
	defined_in_codebase = find_between(
		string, 
		"defined in codebase - ", 
		", currently installed - "
	)
	currently_installed = find_between(
		string, 
		"currently installed - ", 
		"<end>"
	)
	if name not in modules_found:
		modules_found[name] = { 
			"codebase"  : defined_in_codebase,
			"installed" : currently_installed,
			"line" : line
		}


def find_between(s, first, last):
    try:
        start = s.index(first) + len(first)
        end = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ""


def read_contents(file=get_error_file()):
	file = open(file, 'r')
	file = json.load(file)
	for line in file["0"].split("\n"):
		if line_is_valid_module_error(line):
			create_dictonary(line)

		
def search_the_vendor_folder(path, modules):
	dirlist = os.listdir(path)
	for filename in dirlist:
		if options["v"]['status']: print_screen(path + filename)
		if os.path.isdir(path + filename):
			search_the_vendor_folder(
				path + filename + "/",
				modules
			)
		else:
			if filename == 'module.xml':
				search_this_module(path + filename, modules)


def search_this_module(module_xml_path, module):
	module_xml = open(module_xml_path, 'r')
	module_names = list(module.keys())
	for line in module_xml:
		for name in module_names:
			if name in line and 'setup_version' in line and module[name]["codebase"] in line:
				fix_module_file(
					module_xml_path,
					name
				)


def input_prompt(path, name):
	prompt = "Change module " + bcolors.OKBLUE + name + bcolors.ENDC 
	prompt += " from " 
	prompt += modules_found[name]['codebase']
	prompt += " to " 
	prompt += modules_found[name]['installed']
	prompt += "? (y/n): " 
	return prompt


def found_prompt(module_xml_path, name):
	prompt = ("-"*columns)
	prompt += "\n" + bcolors.OKGREEN + "FOUND MODULE AT PATH: " + bcolors.ENDC + module_xml_path + "\n\n"
	prompt += bcolors.HEADER + modules_found[name]['line'] + bcolors.ENDC
	prompt += "\n"+("-"*columns)
	prompt += "\n"
	print_screen(prompt)


def fix_module_file(module_xml_path, name):
	
	while (True):
		if options["i"]["status"] and options["s"]["status"] == False:
			found_prompt(module_xml_path, name)
			prompt = input(input_prompt(module_xml_path, name))
		else:
			prompt = 'y'

		if prompt.lower() == "y":
			try:
				with fileinput.FileInput(module_xml_path, inplace=True, backup='.bak') as file:
					for line in file:
						print_screen(line.replace(modules_found[name]["codebase"], modules_found[name]["installed"]), end='')
				if options["i"]["status"]:
					print_screen()
					print_screen(bcolors.OKGREEN + "Successfully changed: %s" % module_xml_path)
					print_screen(bcolors.ENDC)
				results["success"].append("Successfully changed: %s" % module_xml_path)
				break;

			except:
				print_error("Unexpected error:" + sys.exc_info()[0])
				sys.exit(1)
		

		elif prompt.lower() == "n":
			skip_line = "Skipped module " + name + " at " + module_xml_path
			if options["i"]["status"]:
				print_screen()
				print_screen(bcolors.WARNING + skip_line)
				print_screen(bcolors.ENDC)
			results["skipped"].append("Skipped: %s" % module_xml_path)
			break
		else:
			print_screen("Please enter ( y ) for yes or ( n ) for no")


read_contents()

search_the_vendor_folder(
	MAGENTO_ROOT + "/vendor/", 
	modules_found
)

print_screen()
print_screen("-"*columns)
print_screen(bcolors.OKGREEN + "COMPLETE:" + bcolors.ENDC)
print_screen("-"*columns)
print_screen()

if results["success"]:
	for line in results["success"]:
		print_screen(bcolors.OKGREEN + line + bcolors.ENDC)
	print_screen()
else:
	print_screen("No modules were changed")

if results["skipped"]:
	for line in results["skipped"]:
		print_screen(bcolors.WARNING + line + bcolors.ENDC)
	print_screen()	
