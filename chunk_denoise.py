from pydub import AudioSegment
import os
import shutil
from pydub import AudioSegment
import subprocess

#function chunks audio, denoises it and returns back combined-denoised single audio file
def chunk_denoisex(wav_file):
    aud_file = wav_file
    out_dir_name='DENOISE_CHUNKS'
    out_denoised_dir_name = out_dir_name      
    split_time=60000  # 1min 

    def noise_suppression(dir_name, out_dir_name):    
        subprocess.call(["python -m denoiser.enhance --dns48 --noisy_dir {} --out_dir {} --sample_rate {} --num_workers {} --device cuda".format(dir_name, out_dir_name, 16000, 1)], shell=True)
    def media_conversion(file_name, dir_name):   
        subprocess.call(["ffmpeg -i {} -ar {} -ac {} -bits_per_raw_sample {} -vn {}".format(file_name, 16000, 1, 16, os.path.join(dir_name,'input_audio.wav'))], shell=True)    

    def split_wav_file(audio_file_for_split,dir_chunks_denoiser,split_on=60000):
        newAudio = AudioSegment.from_file(audio_file_for_split)
        print(len(newAudio))
        if os.path.isdir(dir_chunks_denoiser):
            shutil.rmtree(dir_chunks_denoiser)
        os.makedirs(dir_chunks_denoiser)
        file_names_=[]
        if len(newAudio)>split_on:
            count=0
            count1=0
            for itr in range(int(len(newAudio)/split_on)):
                count1=count1 + split_on
                file_names_.append('audio_'+str(itr)+'.wav')
                newAudio_chunk=newAudio[count:count1]
                newAudio_chunk.export(dir_chunks_denoiser+'/audio_'+str(itr)+'.wav', format="wav")
                print(itr,count,count1)
                count=count1
            newAudio_chunk=newAudio[count1:]
            newAudio_chunk.export(dir_chunks_denoiser+'/audio_'+str(int(len(newAudio)/split_on))+'.wav', format="wav")
            file_names_.append('audio_'+str(len(newAudio))+'.wav')
        else:
            newAudio.export(dir_chunks_denoiser+'/audio_'+str(int(len(newAudio)/split_on))+'.wav', format="wav")
    import re       
    
    def merge_wav_files(dir_name): 
        file_names_=os.listdir(dir_name)
        file_names_ = [x for x in file_names_ if re.search('enhanced', x)]
        file_names_ = sorted(file_names_, key=lambda x:float(re.findall("(\d+)",x)[0]))
        combined_sounds = AudioSegment.from_wav(dir_name+'/'+file_names_[0])
        for files in range(1, len(file_names_)):
            print(file_names_[files])
            sound = AudioSegment.from_wav(dir_name+'/'+file_names_[files])

            combined_sounds = combined_sounds + sound
        combined_sounds.export(dir_name+'/'+"combined_out.wav", format="wav")
                
        return  str(dir_name+'/combined_out.wav')

    split_wav_file(aud_file , out_dir_name,split_time)
    noise_suppression(out_dir_name,out_denoised_dir_name)
    merged_file=merge_wav_files(out_denoised_dir_name)
    return(merged_file)

