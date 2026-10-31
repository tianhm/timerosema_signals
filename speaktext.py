
try:
    import pyttsx3

    def speak_text(text):
        if text:
            print(text)
            try:
                ttsengine = pyttsx3.init()
                ttsengine.setProperty('voice', 'zh')
                ttsengine.say(text)
                ttsengine.runAndWait()
                # ttsengine.stop()
            except Exception as e:
                print(f"Speak error: {e}")
except:
    def speak_text(text):
        if text:
            print(text)


if __name__ == "__main__":
    speak_text('安装了语音模块吗?')
    # from espeakng import Speaker
    # s=Speaker(voice='zh')
    # s.say('33')
    # s.say('234234')
    # s.say('晶锐新材')
    # s.voice = 'Chinese_(Mandarin)'
    # s.say('22')
    # print(l)

# {'pty': '5', 'language': 'cmn', 'age': '--', 'gender': 'M', 'voice_name': 'Chinese_(Mandarin)', 'file': 'sit/cmn'}