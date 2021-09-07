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

msg = "Audio Tokenizer"

# Initialize parser & add arguments
parser = argparse.ArgumentParser(description = msg)
parser.add_argument("-url", "--url", help = "youtube URL")
parser.add_argument("-filepath", "--filepath", help = "file path in local")
args = parser.parse_args()

if args.url is None and args.filepath is None:
    sys.exit("ERROR : either enter URL or Path")

# values to change 
path='/home/aswin/ULCA/' 
min_dur = 5              # minimum duration of a valid audio event in seconds
max_dur = 30             # maximum duration of an event
max_silence = 0.075      # maximum duration of tolerated continuous silence within an event
energy_threshold = 50    # threshold of detection



def download_youtubeaudio(url):
    try:
        filepath = str(uuid.uuid4())+".wav"
        output_file=str(uuid.uuid1())+".wav"
        ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filepath,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
            
        }]
        }

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

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
    audio_regions = auditok.split(
        audio_file,
        min_dur=min_dur,     
        max_dur=max_dur,       
        max_silence=max_silence, 
        energy_threshold=energy_threshold
    )

    videouuid = str(uuid.uuid4())
    if args.url:
        foldername = video.title
        row_contents = [args.url , videouuid , video.title , video.duration]
        print(row_contents)

    elif args.filepath:
        foldername = videouuid
        row_contents = [args.filepath , videouuid , " " , ""]
        print(row_contents)
    else:
        pass

    savepath = path + foldername+"/"



    os.makedirs(savepath)
    counter = 0
    for i, r in enumerate(audio_regions):
        filename = r.save(os.path.join(savepath, videouuid + "_region_{meta.start:.3f}-{meta.end:.3f}.wav"))
        print("region saved as: {}".format(filename))
        counter = counter + 1


    row_contents.append(counter)
    with open(path+'url_details.csv', 'a') as f:
        writer = csv.writer(f)
        writer.writerow(row_contents)




    

except Exception as e:
    print(e)




