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
import csv
import pafy
from pytube import YouTube
import wave
import collections
import contextlib
import webrtcvad
import os
import shutil
from pydub import AudioSegment
import mutagen
from mutagen.wave import WAVE
from chunk_denoise import chunk_denoisex

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
PATH='WEBRTC_CHUNKS/'
MIN_DUR = 3              # minimum duration of a valid audio event in seconds
MAX_DUR = 30       # maximum duration of an event
AGGRESSIVENESS = 3
TRIGGER_THRESHOLD = 0.90
USE_DENOISER = True

folder_name= PATH + str(uuid.uuid4())+"/"
if args.desc:
    folder_name = args.desc

if os.path.exists(folder_name):
    shutil.rmtree(folder_name)
os.makedirs(folder_name)


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

def read_wave(path):
    """Reads a .wav file.

    Takes the path, and returns (PCM audio data, sample rate).
    """
    with contextlib.closing(wave.open(path, 'rb')) as wf:
        num_channels = wf.getnchannels()
        assert num_channels == 1
        sample_width = wf.getsampwidth()
        assert sample_width == 2
        sample_rate = wf.getframerate()
        assert sample_rate in (8000, 16000, 32000, 48000)
        pcm_data = wf.readframes(wf.getnframes())
        return pcm_data, sample_rate


class Frame(object):
    """Represents a "frame" of audio data."""
    def __init__(self, bytes, timestamp, duration):
        self.bytes = bytes
        self.timestamp = timestamp
        self.duration = duration
        
def frame_generator(frame_duration_ms, audio, sample_rate):
    """Generates audio frames from PCM audio data.

    Takes the desired frame duration in milliseconds, the PCM data, and
    the sample rate.

    Yields Frames of the requested duration.
    """
    n = int(sample_rate * (frame_duration_ms / 1000.0) * 2)
    offset = 0
    timestamp = 0.0
    duration = (float(n) / sample_rate) / 2.0
    while offset + n < len(audio):
        yield Frame(audio[offset:offset + n], timestamp, duration)
        timestamp += duration
        offset += n

        
        
        
def vad_collector(sample_rate, frame_duration_ms,
                  padding_duration_ms, vad, frames, start_time, end_time):
    """Filters out non-voiced audio frames.

    Given a webrtcvad.Vad and a source of audio frames, yields only
    the voiced audio.

    Uses a padded, sliding window algorithm over the audio frames.
    When more than 90% of the frames in the window are voiced (as
    reported by the VAD), the collector triggers and begins yielding
    audio frames. Then the collector waits until 90% of the frames in
    the window are unvoiced to detrigger.

    The window is padded at the front and back to provide a small
    amount of silence or the beginnings/endings of speech around the
    voiced frames.

    Arguments:

    sample_rate - The audio sample rate, in Hz.
    frame_duration_ms - The frame duration in milliseconds.
    padding_duration_ms - The amount to pad the window, in milliseconds.
    vad - An instance of webrtcvad.Vad.
    frames - a source of audio frames (sequence or generator).

    Returns: A generator that yields PCM audio data.
    """
    num_padding_frames = int(padding_duration_ms / frame_duration_ms)
    # We use a deque for our sliding window/ring buffer.
    ring_buffer = collections.deque(maxlen=num_padding_frames)
    # We have two states: TRIGGERED and NOTTRIGGERED. We start in the
    # NOTTRIGGERED state.
    triggered = False

    voiced_frames = []
    for frame in frames:
        is_speech = vad.is_speech(frame.bytes, sample_rate)

        #sys.stdout.write('1' if is_speech else '0')
        if not triggered:
            ring_buffer.append((frame, is_speech))
            num_voiced = len([f for f, speech in ring_buffer if speech])
            # If we're NOTTRIGGERED and more than 90% of the frames in
            # the ring buffer are voiced frames, then enter the
            # TRIGGERED state.
            if num_voiced > TRIGGER_THRESHOLD * ring_buffer.maxlen:
                triggered = True
                start_time.append(ring_buffer[0][0].timestamp)
                #sys.stdout.write('+(%s)' % (ring_buffer[0][0].timestamp,))
                # We want to yield all the audio we see from now until
                # we are NOTTRIGGERED, but we have to start with the
                # audio that's already in the ring buffer.
                for f, s in ring_buffer:
                    voiced_frames.append(f)
                ring_buffer.clear()
        else:
            # We're in the TRIGGERED state, so collect the audio data
            # and add it to the ring buffer.
            voiced_frames.append(frame)
            ring_buffer.append((frame, is_speech))
            num_unvoiced = len([f for f, speech in ring_buffer if not speech])
            # If more than 90% of the frames in the ring buffer are
            # unvoiced, then enter NOTTRIGGERED and yield whatever
            # audio we've collected.
            if num_unvoiced > TRIGGER_THRESHOLD * ring_buffer.maxlen:
                #sys.stdout.write('-(%s)' % (frame.timestamp + frame.duration))
                end_time.append(frame.timestamp + frame.duration)
                triggered = False
                yield b''.join([f.bytes for f in voiced_frames])
                ring_buffer.clear()
                voiced_frames = []
    if triggered:
        end_time.append(frame.timestamp + frame.duration)
        #sys.stdout.write('-(%s)' % (frame.timestamp + frame.duration))
    #sys.stdout.write('\n')
    # If we have any leftover voiced audio when we run out of input,
    # yield it.
    if voiced_frames:
        yield b''.join([f.bytes for f in voiced_frames])
        
    
def extract_time_stamps(wav_file):
    start_time = []
    end_time = []
    audio, sample_rate = read_wave(wav_file)
    vad = webrtcvad.Vad(AGGRESSIVENESS)
    frames = frame_generator(30, audio, sample_rate)
    frames = list(frames)
    segments = vad_collector(sample_rate, 30, 300, vad, frames, start_time, end_time)

    chunks = 0
    for i, segment in enumerate(segments):
        chunks = chunks + 1
    if chunks != len(start_time):
        print("Error: Segments not broken properly")
        exit
    return start_time, end_time

def  cleanup(folder_name):
    #print(os.listdir(folder_name))
    for wav in os.listdir(folder_name):
        audio = WAVE(os.path.join(folder_name,wav))
        audio_info = audio.info
        length = int(audio_info.length)
        #print(length)
        
        if length < 3 or length > 30:
            os.remove(os.path.join(folder_name,wav))

def chunk_save(wav_file,USE_DENOISER=False):
    print("AGGR")
    print(AGGRESSIVENESS)
    start_time,end_time=(extract_time_stamps(wav_file))

    if USE_DENOISER == True:
            denoised_audio = audio_formatter(chunk_denoisex(audio_file))
            start_time,end_time=(extract_time_stamps(denoised_audio))
            USE_DENOISER = False

    for i in range(len(start_time)): 
        start_time_sec = start_time[i] * 1000 
        end_time_sec  = end_time[i]* 1000

        
        full_dur=(end_time_sec/1000)-(start_time_sec/1000)

        # if full_dur >= MIN_DUR and full_dur <= MAX_DUR :
        newAudio = AudioSegment.from_wav(wav_file)
        newAudio = newAudio[start_time_sec:end_time_sec]
        newAudio.export(folder_name+'/audio_chunk_{}.wav'.format(str(uuid.uuid1())), format="wav")

if args.url:
    print("Passed inputs : ")
    print("----------------")
    url = args.url
    # video = pafy.new(url)
    #video_name = video.title
    video_name = str(uuid.uuid1())
    print("Input URL : " , url)
    print("Input TITLE : " , video_name)

    audio_file = download_youtubeaudio(url)

    video_audio = WAVE(audio_file)
    video_length = video_audio.info.length / 60

    row_contents = [args.url , folder_name , video_name , video_length]

if args.filepath:
    print("Passed inputs : ")
    print("----------------")
    print("Input filepath : " + args.filepath)
    audio_file = audio_formatter(args.filepath)
    wav_audio = WAVE(audio_file)
    audio_length = wav_audio.info.length / 60
    title = os.path.basename(args.filepath )[:-4]
    row_contents = [args.filepath , folder_name , title , audio_length]

try:
    # counter = 0
    # start_time,end_time=(extract_time_stamps(audio_file))


    # if USE_DENOISER:
    #     denoised_audio = audio_formatter(chunk_denoisex(audio_file))
    #     # print(denoised_audio)
    #     print("denoising done")
    #     start_time,end_time=(extract_time_stamps(denoised_audio))
       

    # for i in range(len(start_time)): 
    #     start_time_sec = start_time[i] * 1000 
    #     end_time_sec  = end_time[i]* 1000

        
    #     full_dur=(end_time_sec/1000)-(start_time_sec/1000)

    #     if full_dur >= MIN_DUR and full_dur <= MAX_DUR :
    #         newAudio = AudioSegment.from_wav(audio_file)
    #         newAudio = newAudio[start_time_sec:end_time_sec]
    #         newAudio.export(folder_name+'/audio_chunk_{}.wav'.format(counter), format="wav")
    #         counter = counter+1

    if USE_DENOISER == True:

        chunk_save(audio_file,True)

    else:
        chunk_save(audio_file)

    print("iteration 1 done")
    print((os.listdir(folder_name)))

    # AGGRESSIVENESS = 3
    # for wav in os.listdir(folder_name):
    #         print(wav)
    #         audio = WAVE(os.path.join(folder_name,wav))
    #         audio_info = audio.info
    #         length = int(audio_info.length)
    #         if length > 30 :
    #             print(os.path.join(folder_name,wav))
    #             chunk_save(os.path.join(folder_name,wav),folder_name)
    #             os.remove(os.path.join(folder_name,wav))
    # print("iteration 2 done")
    # print(len(os.listdir(folder_name)))


    # #OPTIONAL, comemnt out
    # TRIGGER_THRESHOLD = 0.5
    # for wav in os.listdir(folder_name):
    #         audio = WAVE(os.path.join(folder_name,wav))
    #         audio_info = audio.info
    #         length = int(audio_info.length)
    #         if length > 30 :
    #             chunk_save(os.path.join(folder_name,wav),folder_name)
    #             os.remove(os.path.join(folder_name,wav))
    # print("iteration 2 done")
    # print(len(os.listdir(folder_name)))

    # #OPTIONAL, comment out
    # TRIGGER_THRESHOLD = 0.1
    # for wav in os.listdir(folder_name):
    #         audio = WAVE(os.path.join(folder_name,wav))
    #         audio_info = audio.info
    #         length = int(audio_info.length)
    #         if length > 30 :
    #             chunk_save(os.path.join(folder_name,wav),folder_name)
                
    print("iteration 3 done")

    print(len(os.listdir(folder_name)))

    cleanup(folder_name)

    folder_item_no = len(os.listdir(folder_name))
    row_contents.append(folder_item_no)
    with open('url_details.csv', 'a') as f:
        writer = csv.writer(f)
        writer.writerow(row_contents)
        print(row_contents)

except Exception as e:
    print(e)
