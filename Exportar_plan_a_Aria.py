#******************************************
# exportar ct y estructuras a eclipse 18/02/22 VD y a vision y a pacs
#******************************************
import statetree, sys, glob, os
import time

from connect import *
from System import (IO, Collections, Windows, ComponentModel)

patient=get_current("Patient")
exam=get_current("Examination")
case=get_current("Case")
plan=get_current("Plan")
beam_set=get_current('BeamSet')

newpath =r"\\srvvariadicom\Dosimetrias"

set = get_current("BeamSet")
set_progress('Enviando a Aria...')
try:
    
    case.ScriptableDicomExport(ExportFolderPath=newpath, BeamSets = ["%s:%s"%(plan.Name, set.DicomPlanLabel)], PhysicalBeamSetDoseForBeamSets =["%s:%s"%(plan.Name, set.DicomPlanLabel)], IgnorePreConditionWarnings=True)
    #enviados.append("Plan "+ plan.Name +" Drr's y Setups enviadas a MOSAIQ")
except:
    msgerror=str(sys.exc_info()[1])
    if msgerror.find("Duplicate")>-1:
        #Windows.MessageBox.Show("Duplicado")
        enviadosconerrores.append("Plan: "+ plan.Name+" NO se pudo enviadar a MOSAIQ")
set_progress('... enviando a Aria')

try:
  case.ScriptableDicomExport(ExportFolderPath=newpath ,Examinations=[exam.Name],RtStructureSetsForExaminations=[exam.Name], IgnorePreConditionWarnings=True)
except:

  Windows.MessageBox.Show("No se ha podido realizar el envio.")
set_progress('Aria OK. Enviando pdf...')
  
### pdf a carpeta compartia en aria______________________________________  

nombredelfichero="\\\srvvariadicom\Dosimetrias\\"+ patient.Name + plan.Name +".pdf"

try:
   set.CreateReport(templateName = "report6", filename = nombredelfichero, ignoreWarnings = True)
   #enviados.append("PDF creado en ESCAN")

except:
    print ('pos no va')
set_progress('Aria y pdf OK. Enviando a VisionRT...')
#******************************************
# vision rt
#******************************************


import sys, math
from System.Windows import *
from System.Windows.Controls import *

sets=[]
structure_set = case.PatientModel.StructureSets[exam.Name]
beam_set = get_current('BeamSet')


try:
        print ("entro en try")         
        case.ScriptableDicomExport(Connection={"Title":"AlignRT6"}, RtStructureSetsForExaminations=[exam.Name],RtStructureSetsReferencedFromBeamSets = [beam_set.BeamSetIdentifier()],RtStructureSetsWithDicomUIDs = [structure_set.SubStructureSets[0].ModificationInfo.DicomUID],BeamSets = [beam_set.BeamSetIdentifier()], IgnorePreConditionWarnings=True)
        for serie in sets:
            print ("entro en el for del try")
            case.ScriptableDicomExport(Connection={"Title":"AlignRT6"},RtStructureSetsForExaminations=[exam.Name], BeamSets = ["%s:%s"%(plan.Name, serie)], IgnorePreConditionWarnings=True)
except:
    
        try:
            for serie in sets:
                print("for del except")
                case.ScriptableDicomExport(Connection={"Title":"AlignRT6"}, RtStructureSetsForExaminations=[exam.Name],RtStructureSetsReferencedFromBeamSets = [beam_set.BeamSetIdentifier()],RtStructureSetsWithDicomUIDs = [structure_set.SubStructureSets[0].ModificationInfo.DicomUID],BeamSets = [beam_set.BeamSetIdentifier()], IgnorePreConditionWarnings=True)
        except:
            Windows.MessageBox.Show("No se ha podido exportar a VisionRT. Es posible que ya esté exportado con anterioridad.","Exportando...")
            sys.exit()  

set_progress('Aria-pdf-Vision OK. Enviando a PACS.....')
#################################################################################################################################################
#                                                   envio del caso actual a pacs
###################################################################################################################################################
try:
      case.ScriptableDicomExport(Connection={"Title":"PACS21"}, Examinations=[exam.Name],IgnorePreConditionWarnings=True)
      enviados.append(exam.Name+" enviado a PACS: ")
except:
      print ( ("El CT ya está en Pacs"))
      #enviadosconerrores.append(exam.Name + " No enviado a PACS: " )
      
try:
      case.ScriptableDicomExport(Connection={"Title":"PACS21"},RtStructureSetsForExaminations=[exam.Name],IgnorePreConditionWarnings=True)
      enviados.append("Estructuras del"+ exam.Name +"  a PACS" )
except:
      print ( ("Las estructuras ya están en pacs"))

i=0
while i<len(sets):        
     try:
         
        case.ScriptableDicomExport(Connection={"Title":"PACS21"}, BeamSets = ["%s:%s"%(plan.Name, sets[i])], TreatmentBeamDrrImages =["%s:%s"%(plan.Name, sets[i])], SetupBeamDrrImages =["%s:%s"%(plan.Name, sets[i])], IgnorePreConditionWarnings=True)
        enviados.append("Plan: "+ plan.Name + " enviado a PACS")            
     except:
               print("tac ya duplicado")                 

     try:
        case.ScriptableDicomExport(Connection={"Title":"PACS21"}, PhysicalBeamSetDoseForBeamSets = ["%s:%s"%(plan.Name, sets[i])], IgnorePreConditionWarnings=True)
     except:
             msgerror=str(sys.exc_info()[1])
     i=i+1 
set_progress('Aria - pdf - Vision - PACS OK. Preparando QA con Octavius1500')
##############    qa
from connect import *
import statetree, sys, glob, os
import time
from connect import *
import sys, math
from System.Windows import *
from System.Windows.Controls import *
from System import (IO, Collections, Windows, ComponentModel)


patient=get_current("Patient")
exam=get_current("Examination")

case=get_current("Case")
plan=get_current("Plan")
beam_set = get_current("BeamSet")
patient=get_current("Patient")

i=0

for elplan in plan.VerificationPlans:
    i=i+1
# Obtener el BeamSet y recorrerlo
beam_set = get_current("BeamSet")
dose_grid = beam_set.GetDoseGrid()
voxel_size_x=dose_grid.VoxelSize.x
help(beam_set.CreateQAPlan)
print ("el plan he pasado el grid")

beam_set.CreateQAPlan(PhantomName="OCTAVIUS 1500 TRUEBEAM", PhantomId="M00005", QAPlanName="QA-Plan"+str(i), IsoCenter={ 'x': -0.01, 'y': -30.29, 'z': -0.34 }, DoseGrid={ 'x': voxel_size_x, 'y': voxel_size_x, 'z': voxel_size_x }, GantryAngle=None, CollimatorAngle=None, CouchRotationAngle=0, ComputeDoseWhenPlanIsCreated=True, RemoveCompensators=False, EnableDynamicTracking=False)
patient.Save()
set_progress('Aria - pdf - Vision - PACS OK. Enviando QA a carpeta compartida (W)')
# Guardado de ficheros
import os
newpath =r"W:\Radiofisica\Fisica\MEDIDAS\verific_pacientes\\"+patient.PatientID
if i>0:
   newpath =r"W:\Radiofisica\Fisica\MEDIDAS\verific_pacientes\\"+patient.PatientID+"_"+plan.Name+"_Verif"+str(i)
if not os.path.exists(newpath):
    os.makedirs(newpath)
plan.VerificationPlans[0].ScriptableQADicomExport(ExportFolderPath=newpath,  QaPlanIdentity ="Phantom", ExportBeamSet=True, ExportExaminationStructureSet=True, ExportBeamSetDose=True, IgnorePreConditionWarnings=True)
set_progress('Paciente enviado a todos los sitios ;)')

Windows.MessageBox.Show("                                   RESULTADOS DEL ENVIO"+chr(13)+"----------------------------------------------------------------------------------"+chr(13)+chr(13)+"            Creo que ya estan para importar en Eclipse, en VisionRT y en el PACS   ;)")