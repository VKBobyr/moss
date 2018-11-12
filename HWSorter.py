from tkinter.filedialog import askdirectory
import os
import os.path as path
from glob import glob
import re
import zipfile
import shutil
import subprocess
from collections import deque

# TODO add a check to see size anomalies
# TODO add a check for spaces in address (moss can't analyze files with spaces)

FAIL = "failed"
OTHER = "other"


def find_all_files(folder):
    # finds all files in folder directory and all subsequent subdirectories
    return glob(path.join(folder, "**", "*.*"), recursive=True)


def unzip_all(base_folder, folder):
    zipfiles = glob(path.join(folder, "**", "*.zip"), recursive=True)

    # unzips all files in the subdirectory
    for zipfile in zipfiles:
        _, prefix, _, _ = separate_assignment(zipfile)
        new_folder = path.join(folder, prefix[:-1])
        unzip(base_folder, zipfile, new_folder)

        # adds the zip file prefix to all files (to maintain naming convention)
        add_prefix_recur(new_folder, prefix)

        # check the new folder for zip files
        unzip_all(base_folder, new_folder)


def add_prefix_recur(folder, prefix):
    files = find_all_files(folder)

    # add prefix to all files in current directory and all subdirectories
    for file in files:
        if (path.splitext(file)[1] == ".zip"):
            continue
        new_name = prefix + get_name_no_ext(file)
        rename_file(file, new_name)


def get_name_no_ext(dir):
    # returns the name of the file with no extension
    name = path.split(dir)[1]
    name = path.splitext(name)[0]
    return name


def rename_file(src, new_name):
    # transfer the extension, if none was provided
    if (path.splitext(new_name)[1] == ""):
        new_name += path.splitext(src)[1]
    # rename
    new_add = path.join(path.split(src)[0], new_name)
    os.rename(src, new_add)


def unzip(base_path, src, to, remove=True):
    folder, name = path.split(src)
    # if we already tried and failed to unzip this zip, skip it
    if (path.basename(folder) == FAIL):
        return

    try:
        # extract the files to 'to'
        zip_ref = zipfile.ZipFile(src, 'r')
        zip_ref.extractall(to)
        zip_ref.close()
        # remove the zip file if the flag is True
        if (remove):
            os.remove(src)

    except Exception as _:
        print("ERROR | Could not extract {}".format(name))
        # move to the failed zips
        move_file(src, path.join(path.join(base_path, FAIL)))


def sort_files(folder, files):
    dictionary = dict()
    dictionary[OTHER] = []
    dictionary[FAIL] = []

    automatic = y_n_input("Perform automatic sorting? (not recommended for assignments with similar file names)")

    # adds all the keys to the dictionary and combines those that match
    [register_assignment(dictionary, x) for x in files]

    keys = list(dictionary.keys())
    # we dont want to search for these keys
    keys.remove(OTHER)
    keys.remove(FAIL)

    # searching queue
    q = deque()
    # final groups of keys; will always contain OTHER and FAIL
    final = deque([[OTHER], [FAIL]])

    # gets a key, finds matches and puts those matches on a queue to search next
    while (len(keys) != 0):
        master = keys.pop()
        final.append([master])
        q.append(master)
        checked = []
        # when the matches run out, repeats the process for the next group
        while (len(q) != 0):
            key1 = q.popleft()
            for key2 in keys:
                if (key2 in checked):
                    continue

                # if the keys match
                if (compare_keys(dictionary, key1, key2)):

                    # in case the user chose manual sorting, they will be asked to confirm the match
                    if (not automatic and not y_n_input("Combine \'{}\' into \'{}\'?".format(key2, master))):
                        checked.append(key2)
                        continue

                    # append the key to the last group
                    final[-1].append(key2)
                    # append the key to the queue to search matches
                    q.append(key2)
                    keys.remove(key2)

    move_files(folder, dictionary, final)


def compare_keys(dictionary, key1, key2):
    # gets the words of the first object from each key (because all values under the same key have the same words)
    words1 = dictionary[key1][0][1]
    words2 = dictionary[key2][0][1]

    return compare_words(words1, words2)


def move_files(folder, dictionary, final, threshold=3):
    # create all needed folders
    for keys in final:
        length = 0
        max = -1
        max_key = ""
        for key in keys:
            values = dictionary[key]
            key_len = len(values)
            if key_len > max:
                max, max_key = (key_len, key)

            length += key_len

        # if there are less than or equal to 'threshold' assignments under a key, skip it
        folder_path = folder
        if length > threshold:
            folder_path = path.join(folder, max_key)

        # otherwise create folder for the key
        if not path.isdir(folder_path):
            os.mkdir(folder_path)

        keys_to_remove = []
        for key in keys:
            # move the assignments which have less than 'threshold' values to the main folder
            if key != max_key or length <= threshold:
                keys_to_remove.append(key)

            # move the files to their keys
            for ass_obj in dictionary[key]:
                old_add = ass_obj[0]
                move_file(old_add, folder_path)

        for key in keys_to_remove:
            del dictionary[key]

    clean_up(folder, dictionary, threshold)


def is_acceptable_key(dictionary, key, threshold):
    length = len(dictionary[key])
    return length > threshold or (key in [OTHER, FAIL] and length > 0)


def compare_words(words1, words2):
    # Returns true if name1 and name2 match; false otherwise. name1 and name2 are lists of words
    # construct full strings out of words
    name1 = "".join(words1)
    name2 = "".join(words2)

    # if the full names match -- return true
    if name1 in name2 or name2 in name1:
        return True

    # check if any of the words in assignment2 are contained in assignment1
    for word in words1:
        if (word in name2):
            return True

    # check if any of the words in assignment1 are contained in assignment2
    for word in words2:
        if (word in name1):
            return True

    return False


def move_file(src, to):
    if (not path.isdir(to)):
        os.mkdir(to)

    name = path.split(src)[1].replace(" ", "_")
    new_add = path.join(to, name)

    os.rename(src, new_add)


def register_assignment(assignment_dictionary, assignment):
    # get the name
    words = get_assignment_name(assignment)
    key = "_".join(words)

    # create an assignment object
    ass_obj = [assignment, words]

    # if the assignment file is not a java file, append it to OTHER
    if (path.splitext(assignment)[1] != ".java"):
        assignment_dictionary[OTHER].append(ass_obj)

    # if the name could not have been made, issue a warning and add to FAIL
    elif (key is None):
        print("WARNING | Could not get name for {}. \nThis file can later be found in the base directory.".format(assignment))
        assignment_dictionary[FAIL].append(ass_obj)

    # if the name matches any of the existing keys, append the assignment to the key
    elif key in assignment_dictionary.keys():
        assignment_dictionary[key].append(ass_obj)

    # otherwise, add the new key to the dictionary
    else:
        assignment_dictionary[key] = [ass_obj]


def y_n_input(prompt=""):
    while(True):
        u_input = input(prompt + " (y/n): ").lower().strip()

        if u_input == "y":
            return True
        elif u_input == "n":
            return False

        print("INPUT ERROR | Unknown input.")


def get_assignment_name(file):
    _, _, name, _ = separate_assignment(file)

    # separates camel case
    name = re.sub(r'((?<=[a-z])[A-Z]|(?<!\A)[A-Z](?=[a-z]))', r' \1', name).lower()

    # split the string with anything that isnt alphanumeric and make it into a list of words
    words = []
    [words.append(word) for word in re.split("[^a-z]", name) if is_acceptable_word(word)]

    # return a list of acceptable words in assignment name
    return words


def separate_assignment(assignment, date_format=r"_\d\d\d\d-\d\d-\d\d-\d\d-\d\d-\d\d_"):
    dir, name = path.split(assignment)
    name, ext = path.splitext(name)

    date = re.search(date_format, name, re.ASCII)
    # if the name did not contain a date (which it should by name convention), print notify the user
    if (date is None):
        if (ext == ".java"):
            print("CAUTION | unable to find date: {}".format(assignment))
        return dir, "", name, ext

    prefix, name = name[: date.end()], name[date.end():]

    return dir, prefix, name, ext


def is_acceptable_word(word):
    # words that can't be inside the word
    # these are usually generic words thrown in randomly in different assignments
    banned_words = ["assignment", "hw"]
    # words that can't equal the word
    # these words are too common and result in false equivalents
    banned_full_words = ["up", "and", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]

    # check if any of the banned words are in the assignment word
    for b_word in banned_words:
        if (b_word in word):
            return False

    return len(word) > 1 and word not in banned_full_words


def clean_up(folder, dictionary, threshold):
    folders = glob(path.join(folder, "*", ""))

    # removes unneccessary folders
    for subdir in folders:
        name = path.basename(subdir[:-1])
        # if the folder name is not one of the keys or the key does not meet the criteria, delete the folder
        if name not in dictionary.keys() or not is_acceptable_key(dictionary, name, threshold):
            shutil.rmtree(subdir)


def run_moss(main_folder, output_file_name="results.txt"):
    main_name = path.basename(main_folder)

    # results will be written to a file called "'main_folder'_'output_file_name'"
    out_file = path.join(main_folder, "{}_{}".format(main_name, output_file_name))
    results = open(out_file, "w")

    # runs moss on each of the assignments
    folders = glob(path.join(main_folder, "*", ""))
    for folder in folders:
        name = path.basename(folder[:-1])
        # we dont want to check these folders
        if (name in [OTHER, FAIL]):
            continue

        print("Checking: {}...".format(name))
        out = run_command("perl mossnet.pl  -l java {}".format(path.join(folder, "*.java")))
        links = get_links(str(out[0]))

        # find the moss link out of the outputs
        if (len(links) > 0):
            out_link = str(links[-1])[: -4]
            results.write("{}:\n{}\n".format(name, out_link))
            print("Output: {}".format(out_link))
        else:
            print("Failed: {}".format(str(out)))

    results.close()
    print("Done. Results can be found in: {}".format(out_file))


def get_links(string):
    # returns a list of urls in a string
    urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\), ]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', string)
    return urls


def run_command(command):
    # runs the command
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    process.wait()
    # gets the output
    out = process.communicate()
    return out


def run():
    # set-up
    folder = askdirectory()

    # sort
    if y_n_input("Would you like to sort?"):
        unzip_all(folder, folder)
        files = find_all_files(folder)
        sort_files(folder, files)
        print("Done sorting. Please check \'{}\' for unsorted files.".format(folder))

    # moss
    if y_n_input("Would you like to run moss?"):
        run_moss(folder)


run()
