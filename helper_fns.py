import re


CBR_REGIONS = {
    "Belconnen": [
        "Aranda", "Belconnen", "Belconnen Town Centre", "Emu Ridge", "Bruce", "Charnwood", "Cook", "Dunlop", "Evatt",
        "Florey", "Flynn", "Fraser", "Giralang", "Hawker", "Higgins", "Holt", "Kippax Centre", "Kaleen", "Latham",
        "Lawson", "Macgregor", "Macnamara", "Macquarie", "Jamison Centre", "Jamison", "McKellar", "Melba", "Page",
        "Scullin", "Spence", "Strathnairn", "Weetangera"
    ],
    "Inner North": [
        "Acton", "Ainslie", "Braddon", "Campbell", "Duntroon", "City", "Canberra City", "Civic", "Dickson",
        "Dickson Centre", "Downer", "Hackett", "Lyneham", "North Lyneham", "O'Connor", "Reid", "Russell", "Turner",
        "Watson"
    ],
    "Inner South": [
        "Barton", "Capital Hill", "Deakin", "Forrest", "Fyshwick", "Griffith", "Manuka", "Kingston", "The Causeway",
        "Narrabundah", "Parkes", "Red Hill", "Yarralumla"
    ],
    "Gungahlin": [
        "Amaroo", "Bonner", "Casey", "Crace", "Forde", "Franklin", "Gungahlin", "Gungahlin Town Centre", "Harrison",
        "Jacka", "Kenny", "Kinlyside", "Mitchell", "Moncrieff", "Ngunnawal", "Nicholls", "Palmerston", "Taylor",
        "Throsby"
    ],
    "Jerrabomberra": [
        "Beard", "Hume", "Oaks Estate", "Symonston", "Jerrabomberra"
    ],
    "Majura": [
        "Canberra Airport", "Airport", "Pialligo", "Majura Park", "Majura"
    ],
    "Molonglo Valley": [
        "Denman Prospect", "Coombs", "Molonglo", "Molonglo Valley", "Sulman", "Whitlam", "Wright"
    ],
    "Tuggeranong": [
        "Banks", "Bonython", "Calwell", "Chisholm", "Conder", "Fadden", "Gilmore", "Gordon", "Gowrie", "Greenway",
        "Tuggeranong Town Centre", "Isabella Plains", "Kambah", "Kambah Village Centre", "Macarthur", "Monash", "Oxley",
        "Richardson", "Theodore", "Wanniassa", "Erindale Centre", "Tuggeranong"
    ],
    "Weston Creek": [
        "Chapman", "Duffy", "Fisher", "Holder", "Rivett", "Stirling", "Waramanga", "Weston", "Weston Creek",
        "Weston Creek Centre"
    ],
    "Woden Valley": [
        "Chifley", "Curtin", "Curtin Centre", "Farrer", "Garran", "Hughes", "Isaacs", "Lyons", "Mawson",
        "Southlands Centre", "O'Malley", "Pearce", "Phillip", "Woden", "Woden Town Centre", "Swinger Hill", "Torrens"
    ]
}


def normalise_suburb(suburb):
    """ Function for consistent normalisation before comparison """
    return re.sub(r'[\W]+', '', suburb.lower())


__NORMALISED_CBR_REGIONS = {normalise_suburb(sub): region for region,suburbs in CBR_REGIONS.items() for sub in suburbs}


def suburb_to_region(suburb):
    """
    Maps CBR suburbs to CBR regions, suburbs sourced from https://en.wikipedia.org/wiki/List_of_Canberra_suburbs
    :param suburb: str of suburb
    :return: str of region
    """
    normalised_suburb = normalise_suburb(suburb)
    return __NORMALISED_CBR_REGIONS.get(normalised_suburb, "Other")
