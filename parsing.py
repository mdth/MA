# ##
# File: parsing.py
# Author: Mailan
# Date: 06.06.16
# Purpose: 
# 	1) Read in rdf file.
# 	2) Find pattern from rdf.  
# 	3) Search pattern in some text with regex.
# 	4) Create statistics about found the grammar pattern in a seperate file.  
# ##

import re
import codecs
from pyparsing import alphas, dblQuotedString, Forward, Literal, Group, OneOrMore, Optional, removeQuotes, Suppress, \
    Word
from pymongo import MongoClient

# GRAMMAR DEFINITION

word = prefix = suffix = Word(alphas)
COLON = Literal(':')
A = Literal('a')
QUOTEDSTRING = dblQuotedString.setParseAction(removeQuotes)

# suppressing following literals 
LPAREN = Suppress('(')
RPAREN = Suppress(')')
DOT = Suppress('.')
COMMA = Suppress(',')
SEMICOLON = Suppress(';')

GETSUFFIX = Suppress(prefix + COLON) + suffix
GETOBJECT = Optional(LPAREN) + OneOrMore((GETSUFFIX | QUOTEDSTRING) + Optional(COMMA)) + Optional(RPAREN)

isA = (GETSUFFIX('subject') | word) + A('relation') + GETSUFFIX('object') + DOT
hasX = GETSUFFIX('subject') + GETSUFFIX('relation') + Group(GETOBJECT)('object') + DOT

search = Forward()
search << (isA | hasX)

snippet_id = 0
pattern_id = 0
p_id = 0


def connecting_to_db():
    """Connecting to localhost MongoDB and initializing needed data base and collections."""
    # default host and port (localhost, 27017)
    client = MongoClient()
    global db
    db = client.database


def read_in_file(filename):
    with open(filename, 'rb') as file:
        return file.read()


def read_in_rdf_file(filename):
    """Returns read in rdf file(s)."""
    cleaned_rdf = []
    with open(filename, 'rb') as file:
        data = file.read()
        rdf_data = data.splitlines()
        for data in rdf_data:
            if data != '':
                cleaned_rdf.append(data)
        return cleaned_rdf


def get_pattern_from_rdf(filename):
    """Returns only pattern list from RDF data."""
    # TODO debug print
    global pattern_id
    global p_id
    global db
    print "Found pattern in RDF."

    data = read_in_rdf_file(filename)
    pattern_list = dict()
    for statements in data:
        has_pattern = ' has pattern: '
        parser_result = search.parseString(statements)
        subject, relation, object = parser_result
        if relation == 'hasPattern':
            pattern_list.update({subject: object})
            # TODO debug line
            print "%s %s %s" % (subject, has_pattern, object)

    for key in pattern_list:
        pattern = pattern_list[key]
        f_pat = {"p_id": p_id, "pattern": key, "single_pattern": []}
        p_id += 1
        print f_pat
        # db.pattern.insert_one(f_pat)
        for item in pattern:
            # pattern_ids = []
            f_pattern = {"pattern_id": pattern_id, "single_pattern": item}
            # pattern_ids.append(pattern_id)
            pattern_id += 1
            print f_pattern
            # db.single_pattern.insert_one(f_pattern)
            # TODO
            # f_pat = {{"p_id" : p_id}, {"$set": {"single_pattern" : pattern_ids}}}
            # print f_pat
            # db.pattern.update_one(f_pat)
    return pattern_list


def compile_pattern(string):
    """Compile a found pattern to search for it in text."""
    return re.compile(string)


def search_pattern(pattern, text):
    """Searches for the pattern found in the rdf in some text. Returns the number of found instances in the text."""
    # TODO add ignorecase?
    s_pattern = compile_pattern('(\s)?' + pattern + '(\s|\.|,)')
    return len(re.findall(s_pattern, text))


def strip_token(pattern, token):
    return token.strip(",'.!?(\u00AB)(\u00BB)") == pattern or token.strip(',".!?(\u00AB)(\u00BB)') == pattern


def word_window(size, pattern, tokens):
    '''Get a word window list with a specific number of words.'''
    split_pattern = pattern.split()
    textsnippets = []
    if len(split_pattern) > 1:
        for ind, token in enumerate(tokens):
            p_index = 0
            i = ind
            while p_index < len(split_pattern):
                if strip_token(split_pattern[p_index], tokens[i]):
                    p_index += 1
                    end_index = i
                    i += 1
                else:
                    break
            if p_index == len(split_pattern):
                print " ".join(tokens[ind - size:i + size])

    else:
        textsnippets = word_window_one_word(size, tokens, pattern)

    return textsnippets


def word_window_one_word(size, tokens, pattern):
    textsnippets = []
    textlength = len(tokens)
    for ind, token in enumerate(tokens):
        if strip_token(pattern, token):
            if (ind - size <= 0) and (ind + size > textlength):
                left_index = size - 1
                while not (ind - left_index) == 0:
                    left_index -= 1
                right_index = size - 1
                while not (ind + right_index) == textlength:
                    right_index -= 1
                textsnippets.append(" ".join(tokens[ind - left_index:ind + right_index]))

            elif ind + size > textlength:
                right_index = size - 1
                while not (ind + right_index) == textlength:
                    right_index -= 1
                textsnippets.append(" ".join(tokens[ind - size:ind + right_index]))

            elif ind - size <= 0:
                left_index = size - 1
                while not (ind - left_index) == 0:
                    left_index -= 1
                textsnippets.append(" ".join(tokens[ind - left_index:ind + size + 1]))
            else:
                textsnippets.append(" ".join(tokens[ind - size:ind + (size + 1)]))
    return textsnippets


def sentence_window(size, pattern, tokens):
    '''Get a word window list with a specific number of sentences. size 0 will return the
    current senctence the pattern is found in. size n will return n sentences left and right
    from the initial sentence.'''
    textsnippets = []
    sentence_boundary = compile_pattern('(\w)*(\u00AB)*(\.|!|\?)+')
    sent_size = size + 1
    for ind, token in enumerate(tokens):
        if strip_token(pattern, token):
            l = 1
            r = 0
            size1 = 0
            size2 = 0

            while size1 < sent_size:
                if (size1 < sent_size) and re.search(sentence_boundary, tokens[ind + r]):
                    size1 += 1
                r += 1

            while size2 < sent_size:
                if ind - l == 0:
                    textsnippets.append(" ".join(tokens[ind - l:ind + r]))
                    size2 += 1
                elif (size2 < sent_size) and re.search(sentence_boundary, tokens[ind - l]):
                    textsnippets.append(" ".join(tokens[ind - (l - 1):ind + (r)]))
                    size2 += 1
                l += 1
    return textsnippets


def find_text_window(text, rdf_pattern, size):
    """Finds text windows with variable size."""
    split_text = text.split()

    for ind, unicode in enumerate(split_text):
        split_text[ind] = unicode.encode('ascii')

    found_pattern = dict()
    # find key
    for key in rdf_pattern:
        pattern = rdf_pattern[key]

        # object only has one key
        if len(pattern) == 1:
            found_pattern.update({key: search_pattern(pattern[0], text)})
            snippets = sentence_window(size, pattern[0], split_text)

            get_snippets(snippets)
        # object has more than one key
        else:
            num_matches = 0
            for item in pattern:
                get_snippets(snippets)
                num_matches += search_pattern(item, text)
                found_pattern.update({key: num_matches})
    # TODO debug print
    print found_pattern


def get_snippets(snippets):
    global db
    global snippet_id
    if len(snippets) > 0:
        for snippet in snippets:
            if not db.snippets.find_one({"text_snippet": snippet}):
                f_snippet = {"snippet_id": snippet_id, "text_snippet": snippet}
                snippet_id += 1
                print f_snippet
                # db.snippets.insert_one(f_snippet)


def get_db_text(rdf_pattern, size):
    for text in db.fackel_corpus.find():
        # print text['text']
        find_text_window(text['text'], rdf_pattern, size)


connecting_to_db()
parsed_RDF = get_pattern_from_rdf('C:/Users/din_m/Google Drive/MA/Prototypen/vhs_qcalculus_mod.rdf')
print
get_db_text(parsed_RDF, 0)