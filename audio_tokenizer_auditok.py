############################################################################################################
# AIM     : Script to chunk audio files from path or youtube URL
# USAGE   : python3 audio_tokenizer.py -url "https://www.youtube.com/watch?v=sXs4LZQhTio"
#           python3 audio_tokenizer.py -filepath "/home/aswin/abc.wav"                            
############################################################################################################

import sys
import argparse
import uuid
import youtube_dl
import os 
import subprocess
import auditok
import csv
import pafy
import os
from pytube import YouTube

msg = "Audio Tokenizer"

# Initialize parser & add arguments
parser = argparse.ArgumentParser(description = msg)
parser.add_argument("-url", "--url", help = "youtube URL")
parser.add_argument("-filepath", "--filepath", help = "file path in local")
parser.add_argument("-desc", "--desc", help = "file description")
args = parser.parse_args()

if args.url is None and args.filepath is None:
    sys.exit("ERROR : either enter URL or Path")

# values to change 
PATH='./AUDITOK_CHUNKS/'
MIN_DUR = 5              # minimum duration of a valid audio event in seconds
MAX_DUR = 45             # maximum duration of an event
MAX_SILENCE = 0.050      # maximum duration of tolerated continuous silence within an event
DEF_ENERGY_THRESHOLD = 50    # threshold of detection



def download_youtubeaudio(url):
    try:
        filepath = str(uuid.uuid4())+".wav"
        output_file=str(uuid.uuid1())+".wav"

        #code to download using youtube_dl [slow]

        # ydl_opts = {
        # 'format': 'bestaudio/best',
        # 'outtmpl': filepath,
        # 'postprocessors': [{
        #     'key': 'FFmpegExtractAudio',
        #     'preferredcodec': 'wav',
        #     'preferredquality': '192',   
        # }]
        # }
        # with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        #     ydl.download([url])

        #code to download using pytube
        yt = YouTube(url)
        yt.streams.filter(type = "audio").first().download()
        os.rename(yt.streams.filter(type = "audio").first().default_filename, filepath)

        # subprocess.call(["python -m denoiser.enhance --dns48 --noisy_dir {} --out_dir {} --sample_rate {} --num_workers {} --device cpu".format(dir_name, dir_name, 16000, 1)], shell=True)
        subprocess.call(["ffmpeg -loglevel error -y -i {} -ar {} -ac {} -bits_per_raw_sample {} -vn {}".format(filepath, 16000, 1, 16, output_file)], shell=True)
        os.remove(filepath)
        return output_file
    except Exception as e:
        print(e)

def audio_formatter(filepath):
    output_file=str(uuid.uuid1())+".wav"
    subprocess.call(["ffmpeg -loglevel error -y -i {} -ar {} -ac {} -bits_per_raw_sample {} -vn {}".format(filepath, 16000, 1, 16, output_file)], shell=True)
    return output_file

def audio_tokenize(var_threshold):
    audio_region = auditok.split(
        audio_file,
        min_dur=MIN_DUR,     
        max_dur=MAX_DUR,       
        max_silence=MAX_SILENCE, 
        energy_threshold=var_threshold
    )
    return audio_region


if args.url:
    print("Passed inputs : ")
    print("----------------")
    url = args.url
    video = pafy.new(url)
    print("Input URL : " , url)
    print("Input TITLE : " , video.title)
    audio_file = download_youtubeaudio(url)

if args.filepath:
    print("Passed inputs : ")
    print("----------------")
    print("Input filepath : " + args.filepath)
    audio_file = audio_formatter(args.filepath)

try:
    max_yield_threshold = DEF_ENERGY_THRESHOLD
    audio_regions = audio_tokenize(max_yield_threshold)
    max_chunk = len(list(enumerate(audio_regions)))

    for i in range(20,80):
        tmp_audio_regions = audio_tokenize(i)
        tmp_no_chunks = len(list(enumerate(tmp_audio_regions)))
        if tmp_no_chunks >= max_chunk:
            max_chunk = tmp_no_chunks
            audio_regions = tmp_audio_regions
            max_yield_threshold = i
  

    print("max threshold : ", max_yield_threshold)
    audio_regions = audio_tokenize(max_yield_threshold)

   
    videouuid = str(uuid.uuid4())
    if args.url:
        # foldername = video.title
        foldername = videouuid
        row_contents = [args.url , videouuid , video.title , video.duration]
        print(row_contents)

    elif args.filepath:
        foldername = videouuid
        row_contents = [args.filepath , videouuid , " " , ""]
        print(row_contents)
    else:
        pass

    savepath = PATH + foldername+"/"


    os.makedirs(savepath)
    counter = 0

    for i, r in enumerate(audio_regions):
        if((r.meta.end - r.meta.start) != MAX_DUR ):
            filename = r.save(os.path.join(savepath, videouuid + "_region_{meta.start:.3f}-{meta.end:.3f}.wav"))
            # print("region saved as: {}".format(filename))
            counter = counter + 1

    for item in audio_regions:
        print(item)

    row_contents.append(counter)
    with open(PATH+'url_details.csv', 'a') as f:
        writer = csv.writer(f)
        writer.writerow(row_contents)
        print(row_contents)

        
except Exception as e:
    print(e)

