from __future__ import division

from PyQt4 import QtGui
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog
from PyQt4.QtCore import *
from PyQt4.QtGui import *

import time 
import login
import home
import add
import error_log
import err_img

import MySQLdb

import sys
import os

import numpy as np
import cv2
import editdistance
from DataLoader import DataLoader, Batch
from Model import Model, DecoderType
from SamplePreprocessor import preprocess

import pyttsx
engine=pyttsx.init()

import warnings
warnings.filterwarnings("ignore")

fname=""
pen_pressure=0
base_angel=0
letter_size=0
spacing=0
slant_angel=0
narrow_count=0
wide_count=0
behavior=""

db = MySQLdb.connect("localhost","root","root","handwritting")
cursor = db.cursor()

class FilePaths:
	"filenames and paths to data"
	fnCharList = 'model/charList.txt'
	fnAccuracy = 'model/accuracy.txt'
	fnTrain = 'data/'
	fnInfer = 'test.png'
	fnCorpus = 'data/corpus.txt'

	
class Login(QtGui.QMainWindow, login.Ui_UserLogin):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self) 
        self.pushButton.clicked.connect(self.log)
        self.pushButton_2.clicked.connect(self.can)
        self.pushButton_3.clicked.connect(self.addNew1)
        
    def log(self):
        i=0
        a=self.lineEdit.text()
        b=self.lineEdit_2.text()
        sql = "SELECT * FROM users WHERE username='%s' and password='%s'" % (a,b)
        try:
            cursor.execute(sql)
            results = cursor.fetchall()
            for row in results:
                i=i+1
        except Exception as e:
           print e
        if i>0:
            print "login success"
            self.hide()
            self.home=home()
            self.home.show()
            
        else:
            print "login failed"
            self.errlog=errlog()
            self.errlog.show()
                    
               
    def can(self):
        sys.exit()

    def addNew1(self):
        self.addNew=addNew()
        self.addNew.show()

class addNew(QtGui.QMainWindow, add.Ui_AdNewAdvertizer):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self)
        self.pushButton.clicked.connect(self.save1)
        self.pushButton_3.clicked.connect(self.can2)

    def can2(self):
        sys.exit()
        
    def save1(self):
        name=self.lineEdit.text()
        email=self.lineEdit_2.text()
        contact=self.lineEdit_3.text()
        uname=self.lineEdit_4.text()
        pwd=self.lineEdit_5.text()
        sql = "INSERT INTO users(name, email, contact, username, password) VALUES ('%s', '%s', '%s', '%s', '%s' )" % (name,email,contact,uname,pwd)
        try:
                cursor.execute(sql)
                self.hide()
                db.commit()
        except:
                db.rollback()
                self.erradd=erradd()
                self.erradd.show()
            

              

class home(QtGui.QMainWindow, home.Ui_Home):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self)
        self.pushButton.clicked.connect(self.selimg)
        self.pushButton_2.clicked.connect(self.seldir)
        self.pushButton_3.clicked.connect(self.nn)
        self.pushButton_5.clicked.connect(self.ex)
        self.pushButton_6.clicked.connect(self.preproc)
        self.pushButton_7.clicked.connect(self.pred)

    def selimg(self):
        global fname
        self.QFileDialog = QtGui.QFileDialog(self)
        #self.QFileDialog.show()
        fname = QFileDialog.getOpenFileName(self, 'Open file','c:\\',"Image files (*.jpg *.png)")
        print fname
        dim = (200, 200) 
        img_to_show=cv2.imread(str(fname))
        resized = cv2.resize(img_to_show, dim, interpolation = cv2.INTER_AREA)
        cv2.imwrite("resized.jpg",resized)
        label = QLabel(self.label_5)
        pixmap = QPixmap("resized.jpg")
        label.setPixmap(pixmap)
        label.resize(pixmap.width(),pixmap.height())
        label.show()

    
    def seldir(self):
        self.QFileDialog = QtGui.QFileDialog(self)
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        print folder
                
        

    def preproc(self):
        global fname
        if fname=="":
            self.errimg=errimg()
            self.errimg.show()
        else:
            filename = fname
            print "file for processing",filename
            image =cv2.imread(str(filename))
            #print type(image)
            cv2.imshow("Original Image", image)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            cv2.imshow("Grayscale Conversion", gray)
            gray = cv2.bilateralFilter(gray, 11, 17, 17)
            cv2.imshow("Bilateral Filter", gray)
            edged = cv2.Canny(gray, 27, 40)
            cv2.imshow("Canny Edges", edged)

    def nn(self):
        def train(model, loader):
            "train NN"
            epoch = 0 # number of training epochs since start
            bestCharErrorRate = float('inf') # best valdiation character error rate
            noImprovementSince = 0 # number of epochs no improvement of character error rate occured
            earlyStopping = 5 # stop training after this number of epochs without improvement
            while True:
                    epoch += 1
                    print('Epoch:', epoch)

                    # train
                    print('Train NN')
                    loader.trainSet()
                    while loader.hasNext():
                            iterInfo = loader.getIteratorInfo()
                            batch = loader.getNext()
                            loss = model.trainBatch(batch)
                            print('Batch:', iterInfo[0],'/', iterInfo[1], 'Loss:', loss)

                    # validate
                    charErrorRate = validate(model, loader)
                    
                    # if best validation accuracy so far, save model parameters
                    if charErrorRate < bestCharErrorRate:
                            print('Character error rate improved, save model')
                            bestCharErrorRate = charErrorRate
                            noImprovementSince = 0
                            model.save()
                            open(FilePaths.fnAccuracy, 'w').write('Validation character error rate of saved model: %f%%' % (charErrorRate*100.0))
                    else:
                            print('Character error rate not improved')
                            noImprovementSince += 1

                    # stop training if no more improvement in the last x epochs
                    if noImprovementSince >= earlyStopping:
                            print('No more improvement since %d epochs. Training stopped.' % earlyStopping)
                            break


        def validate(model, loader):
                "validate NN"
                print('Validate NN')
                loader.validationSet()
                numCharErr = 0
                numCharTotal = 0
                numWordOK = 0
                numWordTotal = 0
                while loader.hasNext():
                        iterInfo = loader.getIteratorInfo()
                        print('Batch:', iterInfo[0],'/', iterInfo[1])
                        batch = loader.getNext()
                        (recognized, _) = model.inferBatch(batch)
                        
                        print('Ground truth -> Recognized')	
                        for i in range(len(recognized)):
                                numWordOK += 1 if batch.gtTexts[i] == recognized[i] else 0
                                numWordTotal += 1
                                dist = editdistance.eval(recognized[i], batch.gtTexts[i])
                                numCharErr += dist
                                numCharTotal += len(batch.gtTexts[i])
                                print('[OK]' if dist==0 else '[ERR:%d]' % dist,'"' + batch.gtTexts[i] + '"', '->', '"' + recognized[i] + '"')
                
                # print validation result
                charErrorRate = numCharErr / numCharTotal
                wordAccuracy = numWordOK / numWordTotal
                print('Character error rate: %f%%. Word accuracy: %f%%.' % (charErrorRate*100.0, wordAccuracy*100.0))
                return charErrorRate

        decoderType = DecoderType.BestPath
      
        # load training data, create TF model
        loader = DataLoader(FilePaths.fnTrain, Model.batchSize, Model.imgSize, Model.maxTextLen)

        # save characters of model for inference mode
        open(FilePaths.fnCharList, 'w').write(str().join(loader.charList))
        
        # save words contained in dataset into file
        open(FilePaths.fnCorpus, 'w').write(str(' ').join(loader.trainWords + loader.validationWords))

        model = Model(loader.charList, decoderType)
        train(model, loader)

        model = Model(loader.charList, decoderType, mustRestore=True)
        validate(model, loader)

    def pred(self):
        def infer(model, fnImg):
            img1=cv2.imread(fnImg, cv2.IMREAD_GRAYSCALE)
            print( "recognize text in image provided by file path")
            img = preprocess(cv2.imread(fnImg, cv2.IMREAD_GRAYSCALE), Model.imgSize)
            batch = Batch(None, [img])
            recognized, probability = model.inferBatch(batch, True)
            print('Recognized:', '"' + recognized[0] + '"')
            self.lineEdit_11.setText(str(recognized[0]))
            pred=str(recognized[0])
	    pred1="Recognized Text From Image is %s"%pred
	    engine.say(pred1)
            engine.runAndWait()
            print('Probability:', probability[0])
            self.lineEdit_10.setText(str(probability[0]))
            cv2.putText(img1,'Prediction: ' + str(recognized[0]),(15, 45),cv2.FONT_HERSHEY_PLAIN,3,200)
            cv2.imshow('Hanwritten Text Recognition', img1)
            cv2.waitKey(0)

        global fname
        decoderType = DecoderType.BestPath
        print(open(FilePaths.fnAccuracy).read())
        model = Model(open(FilePaths.fnCharList).read(), decoderType, mustRestore=True, dump='dump')
        infer(model, str(fname))
    

    def ex(self):
        sys.exit()
        

class errlog(QtGui.QMainWindow, error_log.Ui_Error):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self)
        self.pushButton.clicked.connect(self.ok1)
    def ok1(self):
        self.hide()

class errimg(QtGui.QMainWindow, err_img.Ui_Error):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self)
        self.pushButton.clicked.connect(self.ok1)
    def ok1(self):
        self.hide()



def main():
    app = QtGui.QApplication(sys.argv)  
    form = Login()                 
    form.show()                         
    app.exec_()                         


if __name__ == '__main__':              
    main()                             
