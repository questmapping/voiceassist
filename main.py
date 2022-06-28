import os
import websockets
import asyncio
import base64
import pyaudio
import openai
import json

# load API_KEY_ASSEMBLYAI from .env file if it exists
if os.path.isfile('.env'):
    import dotenv
    dotenv.load_dotenv(dotenv.find_dotenv())
    API_KEY_ASSEMBLYAI = os.getenv('API_KEY_ASSEMBLYAI')
    API_KEY_OPENAI = os.getenv('API_KEY_OPENAI')
else:
    # print error message if .env file does not exist
    print('Error: .env file not found. Please create .env file and add API_KEY_ASSEMBLYAI and API_KEY_OPENAI variables.')


openai.api_key = API_KEY_OPENAI
# Helper Function for OpenAI
def AskGpt3(prompt):
  response = openai.Completion.create(
    model="text-davinci-002",
    prompt= prompt,
    max_tokens=100,
  )
  # We only need the first choice from all the response
  return response['choices'][0]['text']


# Formattiamo i parametri audio per lo Stream
FRAMES_PER_BUFFER = 3200
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
p = pyaudio.PyAudio()

# Creates Stream and starts recording
stream = p.open(
   format=FORMAT,
   channels=CHANNELS,
   rate=RATE,
   input=True,
   frames_per_buffer=FRAMES_PER_BUFFER,
)

# URL for Websocket
WS_URL = "wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000" # same sample rate as audio stream

# funzione per inviare audio e ricevere transcripts

async def SendReceive():
  async with websockets.connect(
      WS_URL, 
      ping_timeout=15,
      ping_interval=5,
      extra_headers={
          "Authorization":API_KEY_ASSEMBLYAI,
      }
  ) as _ws:
    # await for connection. In Async must use await sleep
    await asyncio.sleep(0.1)
    # Create Session
    sessionBegins = await _ws.recv()
    print(sessionBegins)
    print("Sending Messages")
    
    async def Send():
      while True:
        # print("Sending...")
        try:
          data = stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False) # there can be exceptions if stream is slow
          # encode in base64
          data = base64.b64encode(data).decode("utf-8")
          # AssemblyAI needs a JSON with audio data
          json_data = json.dumps({"audio_data":str(data)})
          await _ws.send(json_data)
        # catch some possible errors
        except websockets.exceptions.ConnectionClosedError as e:
          print(e)
          assert e.code == 4008
          break
        except Exception as e:
          assert False, "Not a websocket 4008 error"
        await asyncio.sleep(0.01)
      return True
    
    async def Receive():
      while True:
        try:
            # here we don't send, but receive the json from Assembly and we extract converted text like before
            result_str = await _ws.recv()
            result = json.loads(result_str)
            prompt = result['text']
            if prompt and result['message_type'] == 'FinalTranscript':
              print(f"Io: {prompt}")
              reply = AskGpt3(prompt)
              print(f"Bot: {reply}")
        # always carch some possible errors
        except websockets.exceptions.ConnectionClosedError as e:
            print(e)
            assert e.code == 4008
            break
        except Exception as e:
            assert False, "Not a websocket 4008 error"

    # Combine above functions in a AsyncIO way
    sendResult, receiveResult = await asyncio.gather(Send(), Receive())

# Run the infinite Send - Receive loop
asyncio.run(SendReceive())