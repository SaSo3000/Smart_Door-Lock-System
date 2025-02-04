import face_recognition
import cv2
import numpy as np
from picamera2 import Picamera2
import time
import pickle
from gpiozero import LED
import RPi.GPIO as GPIO
from time import sleep
import I2C_LCD_driver
from mfrc522 import SimpleMFRC522

GPIO.setwarnings(False)
relay_pin = 26
buzzer_pin = 19
button_pin = 17
inbutton_pin = 6
Tag_ID = "904740158974"
camera_flag = False
door = 0

GPIO.setmode(GPIO.BCM)
GPIO.setup(relay_pin, GPIO.OUT)
GPIO.setup(buzzer_pin, GPIO.OUT)
GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(inbutton_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
lcd = I2C_LCD_driver.lcd()

# Create a object for the RFID module
read = SimpleMFRC522()

lcd.lcd_display_string("Booting up",1,3)
for a in range (0,15):
    lcd.lcd_display_string(".",2,a)
    sleep(0.25)

# Load pre-trained face encodings
print("[INFO] loading encodings...")
with open("/home/pi/FaceRecognition/encodings.pickle", "rb") as f:
    data = pickle.loads(f.read())
known_face_encodings = data["encodings"]
known_face_names = data["names"]

# Initialize the camera
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"format": 'XRGB8888', "size": (500, 600)}))
picam2.start()

# Initialize GPIO
output = LED(14)

# Initialize our variables
cv_scaler = 1 # this has to be a whole number

face_locations = []
face_encodings = []
face_names = []
frame_count = 0
start_time = time.time()
fps = 0

# List of names that will trigger the GPIO pin
authorized_names = ["Saunak"]  # Replace with names you wish to authorise THIS IS CASE-SENSITIVE


    
def lock_door():
    global door
    door = 0
    GPIO.output(relay_pin, GPIO.LOW)
    GPIO.output(buzzer_pin, GPIO.LOW)
    print("Door Locked")
    
def unlock_door():
    global door
    door = 1
    GPIO.output(relay_pin, GPIO.HIGH)
    GPIO.output(buzzer_pin, GPIO.LOW)
    print("Door Unlocked")
    time.sleep(10)

def process_frame(frame):
    
    global face_locations, face_encodings, face_names, door
    
    # Resize the frame using cv_scaler to increase performance (less pixels processed, less time spent)
    resized_frame = cv2.resize(frame, (0, 0), fx=(1/cv_scaler), fy=(1/cv_scaler))
    
    # Convert the image from BGR to RGB colour space, the facial recognition library uses RGB, OpenCV uses BGR
    rgb_resized_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
    
    # Find all the faces and face encodings in the current frame of video
    face_locations = face_recognition.face_locations(rgb_resized_frame)
    face_encodings = face_recognition.face_encodings(rgb_resized_frame, face_locations, model='large')
    
    face_names = []
    authorized_face_detected = False
    
    for face_encoding in face_encodings:
    # Calculate the face distances and find the best match index
        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
        best_match_index = np.argmin(face_distances)
        if face_distances[best_match_index] < 0.6:  # Adjust threshold for stricter matching
        # If the best match is close enough, assign the name
            name = known_face_names[best_match_index]
            if name in authorized_names:
                authorized_face_detected = True
        else:
            name = "Unknown"  # Set name to Unknown if no close match
        face_names.append(name)

    
    # Control the GPIO pin based on face detection
    if authorized_face_detected:
        output.on()  # Turn on Pin
        door = 1
        GPIO.output(buzzer_pin, GPIO.HIGH)
        time.sleep(0.5)
        unlock_door()
        
        
    else:
        door = 0
        output.off()  # Turn off Pin
        lock_door()
    
    
    return frame

def draw_results(frame):
    # Display the results
    for (top, right, bottom, left), name in zip(face_locations, face_names):
        # Scale back up face locations since the frame we detected in was scaled
        top *= cv_scaler
        right *= cv_scaler
        bottom *= cv_scaler
        left *= cv_scaler
        
        # Draw a box around the face
        cv2.rectangle(frame, (left, top), (right, bottom), (244, 42, 3), 3)
        
        # Draw a label with a name below the face
        cv2.rectangle(frame, (left -3, top - 35), (right+3, top), (244, 42, 3), cv2.FILLED)
        font = cv2.FONT_HERSHEY_DUPLEX
        cv2.putText(frame, name, (left + 6, top - 6), font, 1.0, (255, 255, 255), 1)
        
        # Add an indicator if the person is authorized
        if name in authorized_names:
            cv2.putText(frame, "Authorized", (left + 6, bottom + 23), font, 0.6, (0, 255, 0), 1)
    
    return frame

def calculate_fps():
    global frame_count, start_time, fps
    frame_count += 1
    elapsed_time = time.time() - start_time
    if elapsed_time > 1:
        fps = frame_count / elapsed_time
        frame_count = 0
        start_time = time.time()
    return fps

def repeat_process(i):
    lcd.lcd_clear()
    lcd.lcd_display_string("Look at camera.",1,0)
    lcd.lcd_display_string("Timer: "+ str(i+1) +"/60",2,0)
    GPIO.output(buzzer_pin,GPIO.HIGH)
    frame = picam2.capture_array()
    
    # Process the frame with the function
    
    processed_frame = process_frame(frame)
    
   
    
    
    # Get the text and boxes to be drawn based on the processed frame
    display_frame = draw_results(processed_frame)
    
    # Calculate and update FPS
    current_fps = calculate_fps()
    
    # Attach FPS counter to the text and boxes
    cv2.putText(display_frame, f"FPS: {current_fps:.1f}", (display_frame.shape[1] - 150, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    
    # Display everything over the video feed.
    cv2.imshow('Video', display_frame)
    
    

while True:
    
    lcd.lcd_clear()
    lcd.lcd_display_string("Place your Tag",1,1)
    
    id,Tag = read.read()
    
    id = str(id)
    if id == Tag_ID or camera_flag==True:
        
        camera_flag = True
  
        
        
    else:
        lcd.lcd_clear()
        lcd.lcd_display_string("Wrong Tag!",1,3)
        GPIO.output(buzzer_pin,GPIO.HIGH)
        sleep(0.3)
        GPIO.output(buzzer_pin,GPIO.LOW)
        sleep(0.3)
        GPIO.output(buzzer_pin,GPIO.HIGH)
        sleep(0.3)
        GPIO.output(buzzer_pin,GPIO.LOW)
        sleep(0.3)
        GPIO.output(buzzer_pin,GPIO.HIGH)
        sleep(0.3)
        GPIO.output(buzzer_pin,GPIO.LOW)
        camera_flag=False
        
      
# By breaking the loop we run this code here which closes everything
    if camera_flag == True:
        
        for i in range(60):
            
            print(i)
            repeat_process(i)
            if door == 1:
                print("Program Restarted")
                GPIO.output(relay_pin, GPIO.LOW)
                lcd.lcd_clear()
                cv2.destroyAllWindows()
                camera_flag=False
                door = 0
                break
            sleep(0.2)
            #if cv2.waitKey(1) == ord("q"):
            if GPIO.input(button_pin) == GPIO.LOW:
                GPIO.output(relay_pin, GPIO.LOW)
                lcd.lcd_clear()
                cv2.destroyAllWindows()
                camera_flag=False
                GPIO.output(relay_pin, GPIO.LOW)
                break
            sleep(0.2)
            
        
    # Break the loop and stop the script if 'q' is pressed
    if cv2.waitKey(1) == ord("q"):
        break
    
    cv2.destroyAllWindows()
    camera_flag=False
    
GPIO.output(buzzer_pin,GPIO.LOW)
cv2.destroyAllWindows()
picam2.stop()
output.off() # Make sure to turn off the GPIO pin when exiting
GPIO.cleanup()