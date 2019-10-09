# -*- coding: utf-8  -*-

import os
import re
import requests
import sys
import time

import pywikibot
from pywikibot.specialbots import UploadRobot

def build_id_file():
    f = open("ids_to_upload.txt", "w+")
    response = requests.get(
        "https://api.geocollections.info/file/?database__acronym=ELM&fields=id&format=json"
    )
    data = response.json()
    numberOfPages = int(re.sub(r'Page [\d]* of ', '', data['page']))

    i = 1
    while i <= numberOfPages:
        pageResponse = requests.get(
            "https://api.geocollections.info/file/?database__acronym=ELM&fields=id&format=json&page=" + str(i)
        )
        pageData = pageResponse.json()
        for entry in pageData['results']:
            f.write('{}\n'.format(entry['id']))
        i += 1
    f.close()


def complete_desc_and_upload(url, pagetitle, image_description, author, date, categories, fileId):
    # complete this once if applies to all files
    description = u"""{{Information
|Description    = """ + image_description + """
|Source         = {{Institution:Estonian Museum of Natural History}}
|Author         = """ + author + """
|Date           = """ + (date if date is not None else '') + """
|Permission     = {{cc-by-sa-4.0}}
|other_fields   = {{EMNH geo}}
}}\n
""" + categories + """
[[Category:Photographs by """ + author + """]]
"""
    keepFilename = True  # set to True to skip double-checking/editing destination filename
    verifyDescription = False  # set to False to skip double-checking/editing description => change to bot-mode
    targetSite = pywikibot.getSite('commons', 'commons')

    bot = UploadRobot(url, description=description, useFilename=pagetitle, keepFilename=keepFilename,
                      verifyDescription=verifyDescription, targetSite=targetSite)
    bot.run()

    # We add the id to the uploaded ids file
    f = open("ids_uploaded.txt", "a")
    f.write('{}\n'.format(fileId))
    f.close()

    # We wait to not upload too quickly
    time.sleep(30)

def replaceCategoryNames(name):
    switcher = {
        "Gastropoda": "Gastropoda fossils",
        "Bivalvia": "Bivalvia fossils"
    }
    return switcher.get(name, name)


def main(args):
    if not os.stat("ids_to_upload.txt").st_size:
        build_id_file()

    with open("ids_to_upload.txt") as f:
        ids = [line.rstrip('\n') for line in f]
    f.close()

    with open("ids_not_uploadable.txt") as f:
        notUploadableIds = [line.rstrip('\n') for line in f]
    f.close()

    with open("ids_uploaded.txt") as f:
        uploadedIds = [line.rstrip('\n') for line in f]
    f.close()

    idsToUpload = list((set(ids) - set(uploadedIds)) - set(notUploadableIds))

    for fileId in idsToUpload:
        time.sleep(5)
        print ("Looking at ID " + fileId)
        response = requests.get(
            "https://api.geocollections.info/file/" + fileId + "?format=json")
        data = response.json()

        fileInfo = data['results'][0]

        if fileInfo['licence__licence_url_en'] != "https://creativecommons.org/licenses/by-sa/4.0":
            print ("Wrong license")
            # We add the id to the not uploadable ids file
            f = open("ids_not_uploadable.txt", "a")
            f.write('{}\n'.format(fileId))
            f.close()
            continue

        fileName = fileInfo['uuid_filename']
        fileFolder1 = fileName[:2]
        fileFolder2 = fileName[2:4]
        fileTitle = fileInfo['description_en']
        fileTitle = fileTitle.replace(".", "_")
        fileTitle = fileTitle.replace("/", "_")

        fileUrl=f"https://files.geocollections.info/{fileFolder1}/{fileFolder2}/{fileName}"
        pagetitle = f"Estonian Museum of Natural History {fileTitle}.jpg"
        date = fileInfo['date_created']
        if (not fileInfo['author__forename']) or (not fileInfo['author__surename']):
            print ("No author name available")
            # We add the id to the not uploadable ids file
            f = open("ids_not_uploadable.txt", "a")
            f.write('{}\n'.format(fileId))
            f.close()
            continue

        author = fileInfo['author__forename'] + " " + fileInfo['author__surename']

        specimensResponse = requests.get(
            "https://api.geocollections.info/file/" + fileId + "?fields=filename,specimen,specimen__specimenidentification__taxon__taxon,specimen__specimenidentification__name,specimen__specimenidentificationgeologies__rock__name,specimen__specimenidentificationgeologies__name&format=json")
        specimensData = specimensResponse.json()
        specimenList = []
        speciesList = []
        rockTypesList = []

        for specimen in specimensData['results']:
            if specimen['specimen__specimenidentification__taxon__taxon'] is not None:
                specimenList.append(specimen['specimen__specimenidentification__taxon__taxon'])
            if specimen['specimen__specimenidentificationgeologies__rock__name'] is not None:
                rockTypesList.append(specimen['specimen__specimenidentificationgeologies__rock__name'])
            if specimen['specimen__specimenidentification__name'] is not None:
                specimenList.append(specimen['specimen__specimenidentification__name'].split(' ', 1)[0])
                speciesList.append(specimen['specimen__specimenidentification__name'])
        specimenList = list(dict.fromkeys(specimenList))
        specimenList = [replaceCategoryNames(x) for x in specimenList]
        speciesList = list(dict.fromkeys(speciesList))

        if not specimenList:
            categories = ""
        else:
            categories = "[[Category:" + "]]\n[[Category:".join(specimenList) + "]]"

        englishDescription = None
        estonianDescription = None

        if speciesList:
            estonianDescription = ', '.join(speciesList) + '.'
            englishDescription = estonianDescription

            if fileInfo['image_description']:
                estonianDescription = estonianDescription + ' ' + fileInfo['image_description']

            if fileInfo['image_description_en']:
                englishDescription = englishDescription + ' ' + fileInfo['image_description_en']
        elif rockTypesList:
            estonianDescription = ', '.join(rockTypesList) + '.'
            englishDescription = ', '.join('"{0}"'.format(rockType) for rockType in rockTypesList) + '.'

            if fileInfo['image_description']:
                estonianDescription = estonianDescription + ' ' + fileInfo['image_description']

            if fileInfo['image_description_en']:
                englishDescription = englishDescription + ' ' + fileInfo['image_description_en']
        else:
            if fileInfo['image_description']:
                estonianDescription = fileInfo['image_description']

            if fileInfo['image_description_en']:
                englishDescription = fileInfo['image_description_en']

        if (not englishDescription) or (not estonianDescription):
            print ("No description available")
            # We add the id to the not uploadable ids file
            f = open("ids_not_uploadable.txt", "a")
            f.write('{}\n'.format(fileId))
            f.close()
            continue

        desc = u"""
                {{et|1=""" + estonianDescription + """ Rohkem teavet [http://geocollections.info/file/""" + str(fileInfo['id']) + """ selle faili] """ + (("""ja [http://geocollections.info/specimen/""" + str(fileInfo['specimen_id']) + """ selle eksemplari] """) if fileInfo['specimen_id'] is not None else "") + """kohta lehel [http://geocollections.info/ geocollections.info]}}
                {{en|1=""" + englishDescription + """ More info [http://geocollections.info/file/""" + str(fileInfo['id']) + """ about this file] """ + ("""and [http://geocollections.info/specimen/""" + str(fileInfo['specimen_id']) + """ about this specimen] """  if fileInfo['specimen_id'] is not None else "") + """at [http://geocollections.info/ geocollections.info]}}
               """

        complete_desc_and_upload(fileUrl, pagetitle, desc, author, date, categories, fileId)

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    finally:
        pywikibot.stopme()
