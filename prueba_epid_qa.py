import System, clr, os
import xml.etree.ElementTree as ET
import shutil

clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Collections")
from System import Windows, Boolean
from System.Windows import *
from System.Windows import Window, Visibility, Application, LogicalTreeHelper
from System.Windows.Controls import ToolTip, ToolTipService
from System.Windows.Forms import MessageBox
from System.Windows.Markup import XamlReader
from System.Threading import Thread, ThreadStart, ApartmentState
from System.IO import StringReader
from System.Xml import XmlReader

from connect import *

# ===== BLOQUE A (reemplaza epid_qa = __import__(...)) =====
import glob
import importlib.util
import numpy as np
import pydicom

LOCAL_UTILS = r"C:\Scripts\ray_epid_qa_utils.py"
VERIFIC_PACIENTES_ROOT = r"W:\Radiofisica\Fisica\MEDIDAS\verific_pacientes"

spec = importlib.util.spec_from_file_location("ray_epid_qa_utils_local", LOCAL_UTILS)
epid_qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(epid_qa)

def invert_exported_dicoms(export_path):
    dcm_files = glob.glob(os.path.join(export_path, "*.dcm"))
    for fp in dcm_files:
        ds = pydicom.dcmread(fp)
        if "PixelData" not in ds:
            continue
        arr = ds.pixel_array.astype(np.float32)
        inv = arr.max() - arr
        inv = np.clip(inv, 0, 65535).astype(np.uint16)
        ds.PixelData = inv.tobytes()
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 0
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.save_as(fp)


def get_patient_nhc(patient_obj):
    possible_attrs = ["PatientID", "PatientId", "MedicalRecordNumber", "PatientNumber"]
    for attr in possible_attrs:
        value = getattr(patient_obj, attr, None)
        if value:
            return str(value).strip()
    raise ValueError("No se pudo obtener el NHC del paciente.")


def get_patient_export_path(patient_obj):
    nhc = get_patient_nhc(patient_obj)
    export_path = os.path.join(VERIFIC_PACIENTES_ROOT, nhc)
    if not os.path.exists(export_path):
        os.makedirs(export_path)
    return export_path

# Global and user defined variables
machine_db = get_current('MachineDB')
ui = get_current('ui')
patient = get_current('Patient')
case = get_current('Case')
beam_set = get_current('BeamSet')
plan = get_current('Plan')
machine = machine_db.GetTreatmentMachine(machineName=beam_set.MachineReference.MachineName, lockMode=None)
version = '.'.join(ui.GetApplicationVersion().split('.')[:3])

phantom_name = r"EPID QA Varian"
phantom_id = r"Phantom"
detector_plane_y = 23
sid_values = {
    "100 SID": 1000,
}
isocenter_values = {
    "100 SID": {'x': 0, 'y': 23, 'z': 25},
}
grid_resolution = {
    'x': 0.1,
    'y': 0.1,
    'z': 0.1
}
# The bool for flood_field_methods refers to whether
# flood field correction should be applied or not.
# The elements refers to 'None', 'Match beam energy', 'Specify beam energy'
flood_field_method = [
    False,
    True,
    True
]
# Only when 'Specify beam energy' is chosen,
# a beam quality id should be given to the action.
# The chosen energy for the 'Specify beam energy'
# will be appended to the list later.
flood_field_beam_quality_id = [
    None,
    None
]

beam_quality_ids = sorted(
    [
        '{} {}'.format(
            int(pbq.NominalEnergy),
            '' if pbq.FluenceMode is None else pbq.FluenceMode
        ).strip()
        for pbq in machine.PhotonBeamQualities
    ],
    key=lambda nrg: (int(nrg.split()[0]), len(nrg))
)


class MyWindow(Window):
    def __init__(self, beam_set, machine):
        self.cacheFile = None
        self.cacheFileExists = False
        self.defVals = self.getDefValues()
        self.window = XamlReader.Load(xr)
        self.window.TopMost = True

        self.beam_set = beam_set
        self.machine = machine
        self.old_text = None

        self.sid_combo_box = LogicalTreeHelper.FindLogicalNode(self.window, 'SIDComboBox')
        items = System.Collections.Generic.List[str]()
        for sid in sid_values.keys():
            items.Add(sid)

        self.sid_combo_box.ItemsSource = items
        if self.defVals.get('epidSID') is not None:
            self.sid_combo_box.SelectedItem = self.defVals['epidSID']
        else:
            self.sid_combo_box.SelectedIndex = 0

        self.export_path_combo_box = LogicalTreeHelper.FindLogicalNode(self.window, 'ExportPathComboBox')
        if self.defVals.get('dirs') is not None:
            for ep in self.defVals['dirs']:
                self.export_path_combo_box.Items.Add(ep)

        if self.defVals.get('dirs_def_val') is not None:
            self.export_path_combo_box.SelectedItem = self.defVals['dirs_def_val']
        else:
            self.export_path_combo_box.SelectedIndex = 0
        self.export_path_combo_box.ToolTip = ToolTip()
        self.export_path_combo_box.ToolTip.Content = self.export_path_combo_box.SelectedItem
        self.export_path_combo_box.SelectionChanged += self.ExportPathChanged

        self.ff_combo_box = LogicalTreeHelper.FindLogicalNode(self.window, 'FFComboBox')
        if self.defVals.get('floodFieldCorrectionSelection') is not None:
            self.ff_combo_box.SelectedIndex = [cbi.Content for cbi in
                                               list(self.ff_combo_box.Items)
                                               ].index(self.defVals['floodFieldCorrectionSelection'])

        self.ffe_combo_box = LogicalTreeHelper.FindLogicalNode(self.window, 'FFEComboBox')
        items = System.Collections.Generic.List[str]()
        for bqi in beam_quality_ids:
            items.Add(bqi)

        self.ffe_combo_box.ItemsSource = items
        if (self.defVals.get('floodFieldEnergy') is not None and
                self.defVals['floodFieldEnergy'] in beam_quality_ids):
            self.ffe_combo_box.SelectedItem = self.defVals['floodFieldEnergy']
        else:
            self.ffe_combo_box.SelectedIndex = 0

        self.select_collimator_angle_radio = LogicalTreeHelper.FindLogicalNode(self.window, 'SelectCollimatorAngle')
        if self.defVals.get('collimatorValue') is not None:
            self.select_collimator_angle_radio.IsChecked = Boolean(True)

        self.collimator_angle_text_box = LogicalTreeHelper.FindLogicalNode(self.window, 'CollimatorAngleTextBox')
        self.collimator_angle_text_box.ToolTip = ToolTip()
        self.collimator_angle_text_box.ToolTip.Visibility = Visibility.Hidden
        ToolTipService.SetShowDuration(self.collimator_angle_text_box, 3000)

        if self.defVals.get('collimatorValue') is not None:
            self.collimator_angle_text_box.Text = self.defVals['collimatorValue']
        self.collimator_angle_text_box.TextChanged += self.collimator_validation

        browse_button = LogicalTreeHelper.FindLogicalNode(self.window, 'BrowseButton')
        browse_button.Click += self.BrowseClicked

        run_button = LogicalTreeHelper.FindLogicalNode(self.window, 'RunButton')
        run_button.Click += self.RunClicked

        close_button = LogicalTreeHelper.FindLogicalNode(self.window, 'CloseButton')
        close_button.Click += self.CloseClicked

        self.save_default_button = LogicalTreeHelper.FindLogicalNode(self.window, 'SaveDefaultButton')
        self.save_default_button.ToolTip = ToolTip()
        if not self.cacheFileExists:
            self.save_default_button.ToolTip.Content = "RayStation preference file not found, default values cannot be saved."
        else:
            self.save_default_button.ToolTip.Content = "Default values are per user / per server."
            self.save_default_button.IsEnabled = True
        self.save_default_button.Click += self.SaveDefaultClicked

        # allow the window to move (borderless windows by default cannot)
        self.window.MouseLeftButtonDown += self.mouseLeftButtonDown

        Application().Run(self.window)

    def mouseLeftButtonDown(self, send, e):
        self.window.DragMove()

    def collimator_validation(self, sender, event):
        collimator_angle_text_box = sender
        new_text = collimator_angle_text_box.Text
        if not new_text.replace('.', '', 1).isdigit():
            collimator_angle_text_box.Text = self.old_text
            collimator_angle_text_box.ToolTip.Content = "Value must be numeric"
            collimator_angle_text_box.ToolTip.Visibility = Visibility.Visible
            collimator_angle_text_box.ToolTip.IsOpen = True
        elif float(new_text) > 360:
            collimator_angle_text_box.Text = self.old_text
            collimator_angle_text_box.ToolTip.Content = "Value must be less than 360"
            collimator_angle_text_box.ToolTip.Visibility = Visibility.Visible
            collimator_angle_text_box.ToolTip.IsOpen = True
        else:
            self.old_text = new_text
            collimator_angle_text_box.ToolTip.Content = ""
            collimator_angle_text_box.ToolTip.Visibility = Visibility.Hidden

    def BrowseClicked(self, sender, event):
        folder_dialog = Windows.Forms.FolderBrowserDialog()
        folder_dialog.ShowNewFolderButton = True
        folder_dialog.Description = "Please select a folder for EPID QA export"
        if folder_dialog.ShowDialog():
            self.export_path_combo_box.Items.Add(folder_dialog.SelectedPath)
            self.export_path_combo_box.SelectedItem = folder_dialog.SelectedPath

    def ExportPathChanged(self, sender, event):
        self.export_path_combo_box.ToolTip.Content = self.export_path_combo_box.SelectedItem

    def SaveDefaultClicked(self, sender, event):
        self.setDefValues()

    def getDefValues(self):
        defValues = {}
        cachePath = os.path.expanduser("~") + r'\AppData\Local\RaySearch_Laboratories_AB'
        self.cacheFile = None
        for root, dirs, files in os.walk(cachePath):
            for name in dirs:
                if version in name:
                    cachePath = os.path.join(root, name)
                    if os.path.exists(os.path.join(cachePath, 'epid.config')):
                        self.cacheFile = os.path.join(cachePath, 'epid.config')
                    else:
                        shutil.copy2(
                            os.path.join(cachePath, 'user.config'),
                            os.path.join(cachePath, 'epid.config')
                        )
                        self.cacheFile = os.path.join(cachePath, 'epid.config')
                    break
        if self.cacheFile is not None:
            shutil.copy2(self.cacheFile, self.cacheFile + '.bak')
            self.cacheFileExists = True
            root = ET.parse(self.cacheFile).getroot()
            settings = root.find('userSettings').find('RaySearch.CorePlatform.EPID.Properties.Settings')
            if settings is not None:
                for setting in settings:
                    if setting.attrib['name'] == 'EPIDSID':
                        defValues['epidSID'] = setting.find('value').text
                    elif setting.attrib['name'] == 'CollimatorValue':
                        defValues['collimatorValue'] = setting.find('value').text
                    elif setting.attrib['name'] == 'FloodFieldCorrectionSelection':
                        defValues['floodFieldCorrectionSelection'] = setting.find('value').text
                    elif setting.attrib['name'] == 'FloodFieldEnergy':
                        defValues['floodFieldEnergy'] = setting.find('value').text
                    elif setting.attrib['name'] == 'EPIDExportFolders':
                        defValues['dirs'] = (setting.find('value').text).split(';')
                    elif setting.attrib['name'] == 'EPIDExportFoldersDefVal':
                        defValues['dirs_def_val'] = setting.find('value').text
                        if defValues['dirs_def_val'] not in defValues['dirs']:
                            defValues['dirs'] = defValues['dirs'][:9].append(defValues['dirs_def_val'])
        return defValues

    def setDefValues(self):
        if self.cacheFileExists:
            root = ET.parse(self.cacheFile).getroot()
            settings = root.find('userSettings').find('RaySearch.CorePlatform.EPID.Properties.Settings')
            if settings is None:
                userSettings = root.find('userSettings')
                settings = ET.SubElement(userSettings, 'RaySearch.CorePlatform.EPID.Properties.Settings')
                epidSID = ET.SubElement(settings, 'setting')
                epidSID.attrib['name'] = 'EPIDSID'
                epidSID.attrib['serializeAs'] = 'String'
                epidSIDVal = ET.SubElement(epidSID, 'value')
                collimatorValue = ET.SubElement(settings, 'setting')
                collimatorValue.attrib['name'] = 'CollimatorValue'
                collimatorValue.attrib['serializeAs'] = 'String'
                collimatorValueVal = ET.SubElement(collimatorValue, 'value')
                floodFieldCorrectionSelection = ET.SubElement(settings, 'setting')
                floodFieldCorrectionSelection.attrib['name'] = 'FloodFieldCorrectionSelection'
                floodFieldCorrectionSelection.attrib['serializeAs'] = 'String'
                floodFieldCorrectionSelectionVal = ET.SubElement(floodFieldCorrectionSelection, 'value')
                floodFieldEnergy = ET.SubElement(settings, 'setting')
                floodFieldEnergy.attrib['name'] = 'FloodFieldEnergy'
                floodFieldEnergy.attrib['serializeAs'] = 'String'
                floodFieldEnergyVal = ET.SubElement(floodFieldEnergy, 'value')
                epidExportFolders = ET.SubElement(settings, 'setting')
                epidExportFolders.attrib['name'] = 'EPIDExportFolders'
                epidExportFolders.attrib['serializeAs'] = 'String'
                epidExportFoldersVal = ET.SubElement(epidExportFolders, 'value')
                epidExportFoldersDefVal = ET.SubElement(settings, 'setting')
                epidExportFoldersDefVal.attrib['name'] = 'EPIDExportFoldersDefVal'
                epidExportFoldersDefVal.attrib['serializeAs'] = 'String'
                epidExportFoldersDefValVal = ET.SubElement(epidExportFoldersDefVal, 'value')
            else:
                for setting in settings:
                    if setting.attrib['name'] == 'EPIDSID':
                        epidSIDVal = setting.find('value')
                    elif setting.attrib['name'] == 'CollimatorValue':
                        collimatorValueVal = setting.find('value')
                    elif setting.attrib['name'] == 'FloodFieldCorrectionSelection':
                        floodFieldCorrectionSelectionVal = setting.find('value')
                    elif setting.attrib['name'] == 'FloodFieldEnergy':
                        floodFieldEnergyVal = setting.find('value')
                    elif setting.attrib['name'] == 'EPIDExportFolders':
                        epidExportFoldersVal = setting.find('value')
                    elif setting.attrib['name'] == 'EPIDExportFoldersDefVal':
                        epidExportFoldersDefValVal = setting.find('value')
            try:
                if self.sid_combo_box.SelectedItem is not None:
                    epidSIDVal.text = self.sid_combo_box.SelectedItem
                if self.collimator_angle_text_box.Text is not None:
                    collimatorValueVal.text = self.collimator_angle_text_box.Text
                if self.ff_combo_box.SelectedItem.Content is not None:
                    floodFieldCorrectionSelectionVal.text = self.ff_combo_box.SelectedItem.Content
                if self.ffe_combo_box.SelectedItem is not None:
                    floodFieldEnergyVal.text = self.ffe_combo_box.SelectedItem
                if self.defVals.get('dirs') is None:
                    self.defVals['dirs'] = []
                if self.export_path_combo_box.SelectedItem is not None:
                    if self.export_path_combo_box.SelectedItem not in self.defVals['dirs']:
                        self.defVals['dirs'].insert(0, self.export_path_combo_box.SelectedItem)
                if len(self.defVals['dirs']) > 0:
                    epidExportFoldersVal.text = ';'.join(self.defVals['dirs'][:10])
                if self.export_path_combo_box.SelectedItem is not None:
                    epidExportFoldersDefValVal.text = self.export_path_combo_box.SelectedItem
            except NameError:
                MessageBox.Show(
                    'Something went wrong, preferences could not be saved. A setting was not found in the config file, or the config file itself was not found.')
                return
            try:
                with open(self.cacheFile, 'w') as f:
                    f.write(ET.tostring(indent(root), encoding='utf8').decode('utf8'))
            except Exception as e:
                print(e)
            if os.path.getsize(self.cacheFile) == 0:
                shutil.copy2(self.cacheFile + '.bak', self.cacheFile)
                MessageBox.Show('Something went wrong, preferences could not be saved')
            else:
                MessageBox.Show('Default values saved.')

    def update_dirs(self):
        root = ET.parse(self.cacheFile).getroot()
        settings = root.find('userSettings').find('RaySearch.CorePlatform.EPID.Properties.Settings')
        if settings is None:
            userSettings = root.find('userSettings')
            settings = ET.SubElement(userSettings, 'RaySearch.CorePlatform.EPID.Properties.Settings')
            epidExportFolders = ET.SubElement(settings, 'setting')
            epidExportFolders.attrib['name'] = 'EPIDExportFolders'
            epidExportFolders.attrib['serializeAs'] = 'String'
            epidExportFoldersVal = ET.SubElement(epidExportFolders, 'value')
        else:
            for setting in settings:
                if setting.attrib['name'] == 'EPIDExportFolders':
                    epidExportFoldersVal = setting.find('value')

        epidExportFoldersVal.text = ';'.join(self.defVals['dirs'])
        try:
            with open(self.cacheFile, 'w') as f:
                f.write(ET.tostring(indent(root), encoding='utf8').decode('utf8'))
        except Exception as e:
            print(e)
        if os.path.getsize(self.cacheFile) == 0:
            shutil.copy2(self.cacheFile + '.bak', self.cacheFile)

    def RunClicked(self, sender, event):
        # Validate input
        selected_sid = self.sid_combo_box.SelectedItem
        selected_flood_field_method_index = self.ff_combo_box.SelectedIndex
        selected_beam_quality = self.ffe_combo_box.SelectedItem

        flood_field_beam_quality_id.append(selected_beam_quality)

        if selected_sid is None:
            MessageBox.Show('No EPID SID selected', 'Cannot run EPID QA')
            return
        select_collimator_angle = LogicalTreeHelper.FindLogicalNode(self.window, 'SelectCollimatorAngle')
        if select_collimator_angle.IsChecked:
            collimator_angle = self.collimator_angle_text_box.Text
            try:
                collimator_angle = int(collimator_angle)
            except:
                MessageBox.Show('Invalid input for collimator angle', 'Cannot run EPID QA')
                return
            if collimator_angle != '':
                if collimator_angle > 360:
                    MessageBox.Show('Collimator angle must be less than 360 degrees', 'Cannot run EPID QA')
                    return
                if machine.SupportedCollimatorAngles.x > machine.SupportedCollimatorAngles.y:
                    if collimator_angle > machine.SupportedCollimatorAngles.y and collimator_angle < machine.SupportedCollimatorAngles.x:
                        MessageBox.Show('Collimator angle must be within the supported angles of the machine',
                                        'Cannot run EPID QA')
                        return
                else:
                    if collimator_angle < machine.SupportedCollimatorAngles.x or collimator_angle > machine.SupportedCollimatorAngles.y:
                        MessageBox.Show('Collimator angle must be within the supported angles of the machine',
                                        'Cannot run EPID QA')
                        return
        else:
            collimator_angle = ''
        try:
            export_path = get_patient_export_path(patient)
        except Exception as exc:
            MessageBox.Show(
                u'No se pudo crear/usar la carpeta de exportación por NHC.\n{}'.format(exc),
                'Cannot run EPID QA'
            )
            return

        self.window.Hide()
        if self.cacheFileExists:
            if self.defVals.get('dirs') is None:
                self.defVals['dirs'] = []
            if export_path in self.defVals['dirs']:
                self.defVals['dirs'].pop(self.defVals['dirs'].index(export_path))
            self.defVals['dirs'].insert(0, export_path)
            self.update_dirs()

        print('****************************')
        print('     Computation started    ')
        print('****************************')

        # Setup input to EPID method
        isocenter = isocenter_values[selected_sid]
        sid = sid_values[selected_sid]
        machine_sad = machine.Physics.SourceAxisDistance

        # ===== BLOQUE B (reemplaza la llamada compute en RunClicked) =====
        target = epid_qa.ray_epid_qa_utils if hasattr(epid_qa, "ray_epid_qa_utils") else epid_qa

        target.compute_epid_qa_response(
            patient, plan, self.beam_set, grid_resolution, phantom_name, phantom_id,
            collimator_angle, sid, isocenter, detector_plane_y, machine_sad, ui,
            export_path, flood_field_method[selected_flood_field_method_index],
            flood_field_beam_quality_id[selected_flood_field_method_index]
        )

        invert_exported_dicoms(export_path)

        print('****************************')
        print('       Export finished      ')
        print('****************************')
        MessageBox.Show('Export finished', 'Export finished')
        self.window.Close()

    def CloseClicked(self, sender, event):
        self.window.Close()


def run_window(beam_set, machine):
    window = MyWindow(beam_set, machine)


def export_qa_plan_to_aria(verification_plan):
    qa_export_root = r"\\srvvariadicom\Dosimetrias"
    if not os.path.exists(qa_export_root):
        os.makedirs(qa_export_root)

    qa_beam_set = verification_plan.BeamSet
    qa_beam_set_id = qa_beam_set.DicomPlanLabel
    export_attempts = [
        ("ScriptableDicomExport_ObjectRefs", dict(
            ExportFolderPath=qa_export_root,
            BeamSets=[qa_beam_set],
            PhysicalBeamSetDoseForBeamSets=[qa_beam_set],
            PhysicalBeamDosesForBeamSets=[qa_beam_set],
            IgnorePreConditionWarnings=True
        )),
        ("ScriptableDicomExport_ObjectRefs_NoFlags", dict(
            ExportFolderPath=qa_export_root,
            BeamSets=[qa_beam_set],
            PhysicalBeamSetDoseForBeamSets=[qa_beam_set],
            PhysicalBeamDosesForBeamSets=[qa_beam_set],
        )),
        ("ScriptableDicomExport_BeamSetLabel", dict(
            ExportFolderPath=qa_export_root,
            BeamSets=[qa_beam_set_id],
            PhysicalBeamSetDoseForBeamSets=[qa_beam_set_id],
            PhysicalBeamDosesForBeamSets=[qa_beam_set_id],
            IgnorePreConditionWarnings=True
        )),
    ]

    errors = []
    for attempt_name, kwargs in export_attempts:
        try:
            case.ScriptableDicomExport(**kwargs)
            return qa_export_root
        except Exception as exc:
            errors.append("{}: {}".format(attempt_name, exc))

    raise Exception(
        'No se pudo exportar el QA plan (RT Plan + RT Dose) a {}.\n'
        'Errores de intentos:\n- {}'.format(qa_export_root, '\n- '.join(errors))
    )


def run_epid_qa_automatic():
    selected_sid = "100 SID"
    collimator_angle = ''
    selected_flood_field_method_index = 0  # None

    try:
        export_path = get_patient_export_path(patient)
    except Exception as exc:
        MessageBox.Show(
            u'No se pudo crear/usar la carpeta de exportación por NHC.\n{}'.format(exc),
            'Cannot run EPID QA'
        )
        return

    print('****************************')
    print('     Computation started    ')
    print('****************************')

    isocenter = isocenter_values[selected_sid]
    sid = sid_values[selected_sid]
    machine_sad = machine.Physics.SourceAxisDistance
    target = epid_qa.ray_epid_qa_utils if hasattr(epid_qa, "ray_epid_qa_utils") else epid_qa

    qa_count_before = plan.VerificationPlans.Count

    target.compute_epid_qa_response(
        patient, plan, beam_set, grid_resolution, phantom_name, phantom_id,
        collimator_angle, sid, isocenter, detector_plane_y, machine_sad, ui,
        export_path, flood_field_method[selected_flood_field_method_index],
        flood_field_beam_quality_id[selected_flood_field_method_index]
    )

    invert_exported_dicoms(export_path)

    qa_count_after = plan.VerificationPlans.Count
    if qa_count_after > qa_count_before:
        qa_plan = plan.VerificationPlans[qa_count_after - 1]
        try:
            aria_export_path = export_qa_plan_to_aria(qa_plan)
            print('QA RT Plan/RT Dose exportado en: {}'.format(aria_export_path))
        except Exception as exc:
            warning_msg = u'No se pudo exportar automáticamente QA RT Plan/RT Dose.\n{}'.format(exc)
            print(warning_msg)
            MessageBox.Show(warning_msg, 'QA export warning')
    else:
        print('No se encontró un nuevo QA plan para exportar a ARIA.')

    print('****************************')
    print('       Export finished      ')
    print('****************************')
    MessageBox.Show('Export finished', 'Export finished')


def indent(elem, level=0):
    i = "\n" + level * "  "
    j = "\n" + (level - 1) * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for subelem in elem:
            indent(subelem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = j
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = j
    return elem


# XAML code
xaml = r"""<Window
       xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
       xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
       xmlns:Controls="http://schemas.raysearch.com/coreui/wpf/controls"
       Title="Compute and export EPID QA response" SizeToContent="Height"  Width="440" Background="#FF2C2C2C"
       BorderBrush="#FF000000" BorderThickness="1,1,1,1" Foreground="#FFE2E2E2" ShowInTaskbar="False" WindowStartupLocation="CenterScreen" ResizeMode="NoResize" WindowStyle="None">
    <Window.Resources>
        <BooleanToVisibilityConverter x:Key="BoolToVisConverter"/>
        <SolidColorBrush x:Key="okButtonMouseOver" Color="#FF666666" />
        <SolidColorBrush x:Key="DarkBrush" Color="#FF555555" />
        <SolidColorBrush x:Key="PressedBrush" Color="#FF555555" />
        <SolidColorBrush x:Key="ControlMouseOverColor" Color="#FF555555" />
        <SolidColorBrush x:Key="ControlPressedColor" Color="#FF555555" />
        <SolidColorBrush x:Key="DisabledForegroundBrush" Color="#FFE2E2E2" Opacity="0.4" />
        <SolidColorBrush x:Key="DisabledBackgroundBrush" Color="#FF222222" />
        <SolidColorBrush x:Key="SelectedBackgroundBrush" Color="#DDD" />
        <SolidColorBrush x:Key="NormalBorderBrush" Color="Black" />
        <SolidColorBrush x:Key="PressedBorderBrush" Color="#FFE88208" />
        <SolidColorBrush x:Key="DisabledBorderBrush" Color="#FF2C2C2C" />
        <SolidColorBrush x:Key="SolidBorderBrush" Color="#888" />
        <SolidColorBrush x:Key="LightBorderBrush" Color="#AAA" />
        <SolidColorBrush x:Key="GlyphBrush" Color="#FFE2E2E2" />
        <SolidColorBrush x:Key="{x:Static SystemColors.ControlTextBrushKey}"
                 Color="#FFE2E2E2"/>
        <SolidColorBrush x:Key="{x:Static SystemColors.WindowTextBrushKey}"
                 Color="#FFE2E2E2"/>
        <SolidColorBrush x:Key="WindowBackgroundBrush" Color="#FF222222" />
        <SolidColorBrush x:Key="LightColorBrush" Color="#DDD" />
        <LinearGradientBrush x:Key="NormalBrush" StartPoint="0,0" EndPoint="0,1">
            <GradientBrush.GradientStops>
                <GradientStopCollection>
                    <GradientStop Color="#FF222222" Offset="0.0"/>
                    <GradientStop Color="#FF222222" Offset="1.0"/>
                </GradientStopCollection>
            </GradientBrush.GradientStops>
        </LinearGradientBrush>
        <Style TargetType="TextBox" x:Key="Textbox">
            <Setter Property="Foreground" Value="#FFE2E2E2"/>
            <Setter Property="Background" Value="#FF555555"/>
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="{x:Type TextBox}">
                        <Border x:Name="border"
                            CornerRadius="2"
                            BorderBrush="black"
                            BorderThickness="1"
                            Background="#FF222222"
                            >
                            <ScrollViewer x:Name="PART_ContentHost"
                                Focusable="false"
                                HorizontalScrollBarVisibility="Hidden"
                                VerticalScrollBarVisibility="Hidden"/>
                        </Border>
                        <ControlTemplate.Triggers>
                            <Trigger Property="IsMouseOver" Value="true">
                                <Setter Property="BorderBrush" TargetName="border" Value="Black"/>
                                <Setter Property="Foreground" Value="#FFE2E2E2" />

                            </Trigger>
                            <Trigger Property="IsFocused" Value="true">
                                <Setter Property="Foreground" Value="#FFE2E2E2" />
                                <Setter Property="BorderBrush" TargetName="border" Value="Black"/>
                            </Trigger>
                        </ControlTemplate.Triggers>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
        </Style>

        <ControlTemplate x:Key="ComboBoxToggleButton" TargetType="ToggleButton">
            <Grid>
                <Grid.ColumnDefinitions>
                    <ColumnDefinition />
                    <ColumnDefinition Width="1" />
                    <ColumnDefinition Width="20" />
                </Grid.ColumnDefinitions>
                <Border x:Name="Border" Grid.ColumnSpan="3" CornerRadius="2" Background="{StaticResource NormalBrush}"
                    BorderBrush="{StaticResource NormalBorderBrush}" BorderThickness="1" />
                <Border Grid.Column="0" CornerRadius="2,0,0,2" Margin="1" Background="{StaticResource WindowBackgroundBrush}"
                    BorderBrush="{StaticResource NormalBorderBrush}" BorderThickness="0,0,1,0" />

                <Path x:Name="Arrow" Grid.Column="2" Fill="{StaticResource GlyphBrush}" HorizontalAlignment="Center"
                      VerticalAlignment="Center" Data="M 0 0 L 4 4 L 8 0 Z"/>
            </Grid>
            <ControlTemplate.Triggers>
                <Trigger Property="ToggleButton.IsMouseOver" Value="true">
                    <Setter TargetName="Border" Property="Background" Value="{StaticResource DarkBrush}" />
                </Trigger>
                <Trigger Property="ToggleButton.IsChecked" Value="true">
                    <Setter TargetName="Border" Property="Background" Value="{StaticResource PressedBrush}" />
                </Trigger>
                <Trigger Property="IsEnabled" Value="False">
                    <Setter TargetName="Border" Property="Background" Value="{StaticResource DisabledBackgroundBrush}" />
                    <Setter TargetName="Border" Property="BorderBrush" Value="{StaticResource DisabledBorderBrush}" />
                    <Setter Property="Foreground" Value="{StaticResource DisabledForegroundBrush}"/>
                    <Setter TargetName="Arrow" Property="Fill" Value="{StaticResource DisabledForegroundBrush}" />
                </Trigger>
            </ControlTemplate.Triggers>
        </ControlTemplate>

        <ControlTemplate x:Key="ComboBoxTextBox" TargetType="TextBox">
            <Border x:Name="PART_ContentHost" Focusable="False" Background="{TemplateBinding Background}" />
        </ControlTemplate>

        <Style x:Key="OKRoundCorner" TargetType="{x:Type Button}">
            <Setter Property="HorizontalContentAlignment" Value="Center"/>
            <Setter Property="VerticalContentAlignment" Value="Center"/>
            <Setter Property="Padding" Value="1"/>
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="{x:Type Button}">
                        <Grid x:Name="grid">
                            <Border x:Name="Border" CornerRadius="10" BorderBrush="#FFE88208" Opacity="0.85" BorderThickness="1" Width="55" Height="20" SnapsToDevicePixels="True">
                                <Border.Background>
                                    <SolidColorBrush Color="#FF555555"/>
                                </Border.Background>
                                <ContentPresenter HorizontalAlignment="Center"
                                          VerticalAlignment="Center"
                                          TextElement.Foreground="#FFE2E2E2"/>
                            </Border>
                        </Grid>
                        <ControlTemplate.Triggers>
                            <Trigger Property="ToggleButton.IsMouseOver" Value="true">
                                <Setter TargetName="Border" Property="Background" Value="{StaticResource okButtonMouseOver}" />
                            </Trigger>
                        </ControlTemplate.Triggers>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
        </Style>

        <Style x:Key="CancelRoundCorner" TargetType="{x:Type Button}">
            <Setter Property="HorizontalContentAlignment" Value="Center"/>
            <Setter Property="VerticalContentAlignment" Value="Center"/>
            <Setter Property="Padding" Value="1"/>
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="{x:Type Button}">
                        <Grid x:Name="grid">
                            <Border x:Name="Border" CornerRadius="10" BorderBrush="#FFE2E2E2" Opacity="0.88" BorderThickness="1" Width="70" Height="20" SnapsToDevicePixels="True">
                                <ContentPresenter HorizontalAlignment="Center"
                                          VerticalAlignment="Center"
                                          TextElement.Foreground="#FFE2E2E2"/>
                            </Border>
                        </Grid>
                        <ControlTemplate.Triggers>
                            <Trigger Property="ToggleButton.IsMouseOver" Value="true">
                                <Setter TargetName="Border" Property="Background" Value="{StaticResource DarkBrush}" />
                            </Trigger>
                        </ControlTemplate.Triggers>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
        </Style>

        <Style x:Key="DefaultRoundCorner" TargetType="{x:Type Button}">
            <Setter Property="HorizontalContentAlignment" Value="Center"/>
            <Setter Property="VerticalContentAlignment" Value="Center"/>
            <Setter Property="Padding" Value="1"/>
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="{x:Type Button}">
                        <Grid x:Name="grid">
                            <Border x:Name="Border" CornerRadius="10" BorderBrush="#FFE2E2E2" Opacity="0.88" BorderThickness="1" Width="86" Height="20" SnapsToDevicePixels="True">
                                <ContentPresenter HorizontalAlignment="Center"
                                          VerticalAlignment="Center"
                                          TextElement.Foreground="#FFE2E2E2"/>
                            </Border>
                        </Grid>
                        <ControlTemplate.Triggers>
                            <Trigger Property="ToggleButton.IsMouseOver" Value="true">
                                <Setter TargetName="Border" Property="Background" Value="{StaticResource DarkBrush}" />
                            </Trigger>
                        </ControlTemplate.Triggers>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
        </Style>

        <Style x:Key="xButton" TargetType="{x:Type Button}">
            <Setter Property="HorizontalContentAlignment" Value="Center"/>
            <Setter Property="VerticalContentAlignment" Value="Center"/>
            <Setter Property="Padding" Value="1"/>
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="{x:Type Button}">
                            <Border>
                            <Border.Style>
                                <Style TargetType="{x:Type Border}">
                                    <Style.Triggers>
                                        <Trigger Property="IsMouseOver" Value="True">
                                            <Setter Property="Background" Value="#FF555555"/>
                                        </Trigger>
                                    </Style.Triggers>
                                </Style>
                            </Border.Style>
                            <Grid>
                                <ContentPresenter></ContentPresenter>
                            </Grid>
                        </Border>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
        </Style>

        <Style x:Key="{x:Type ComboBox}" TargetType="ComboBox">
            <Setter Property="SnapsToDevicePixels" Value="true"/>
            <Setter Property="OverridesDefaultStyle" Value="true"/>
            <Setter Property="ScrollViewer.HorizontalScrollBarVisibility" Value="Auto"/>
            <Setter Property="ScrollViewer.VerticalScrollBarVisibility" Value="Auto"/>
            <Setter Property="ScrollViewer.CanContentScroll" Value="true"/>
            <Setter Property="MinWidth" Value="120"/>
            <Setter Property="MinHeight" Value="20"/>
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="ComboBox">
                        <Grid>
                            <ToggleButton Name="ToggleButton" Template="{StaticResource ComboBoxToggleButton}" Grid.Column="2" Focusable="false"
                                    IsChecked="{Binding Path=IsDropDownOpen,Mode=TwoWay,RelativeSource={RelativeSource TemplatedParent}}" ClickMode="Press"/>
                            <ContentPresenter Name="ContentSite" IsHitTestVisible="False" Content="{TemplateBinding SelectionBoxItem}"
                                    ContentTemplate="{TemplateBinding SelectionBoxItemTemplate}"
                                    ContentTemplateSelector="{TemplateBinding ItemTemplateSelector}"
                                    Margin="3,3,23,3" VerticalAlignment="Center" HorizontalAlignment="Left" />
                            <TextBox x:Name="PART_EditableTextBox" Style="{x:Null}" Template="{StaticResource ComboBoxTextBox}"
                                    HorizontalAlignment="Left" VerticalAlignment="Center" Margin="3,3,23,3"
                                    Focusable="True" Background="Transparent" Visibility="Hidden"
                                    IsReadOnly="{TemplateBinding IsReadOnly}"/>
                            <Popup Name="Popup" Placement="Bottom" IsOpen="{TemplateBinding IsDropDownOpen}"
                                    AllowsTransparency="True" Focusable="False" PopupAnimation="Slide">
                                <Grid Name="DropDown" SnapsToDevicePixels="True" MinWidth="{TemplateBinding ActualWidth}"
                                        MaxHeight="{TemplateBinding MaxDropDownHeight}">
                                    <Border x:Name="DropDownBorder" Background="{StaticResource WindowBackgroundBrush}"
                                        BorderThickness="1" BorderBrush="{StaticResource SolidBorderBrush}"/>
                                    <ScrollViewer Margin="4,6,4,6" SnapsToDevicePixels="True">
                                        <StackPanel IsItemsHost="True" KeyboardNavigation.DirectionalNavigation="Contained" />
                                    </ScrollViewer>
                                </Grid>
                            </Popup>
                        </Grid>
                        <ControlTemplate.Triggers>
                            <Trigger Property="HasItems" Value="false">
                                <Setter TargetName="DropDownBorder" Property="MinHeight" Value="95"/>
                            </Trigger>
                            <Trigger Property="IsEnabled" Value="false">
                                <Setter Property="Foreground" Value="{StaticResource DisabledForegroundBrush}"/>
                            </Trigger>
                            <Trigger Property="IsGrouping" Value="true">
                                <Setter Property="ScrollViewer.CanContentScroll" Value="false"/>
                            </Trigger>
                            <Trigger SourceName="Popup" Property="Popup.AllowsTransparency" Value="true">
                                <Setter TargetName="DropDownBorder" Property="CornerRadius" Value="4"/>
                                <Setter TargetName="DropDownBorder" Property="Margin" Value="0,2,0,0"/>
                            </Trigger>
                            <Trigger Property="IsEditable" Value="true">
                                <Setter Property="IsTabStop" Value="false"/>
                                <Setter TargetName="PART_EditableTextBox" Property="Visibility"    Value="Visible"/>
                                <Setter TargetName="ContentSite" Property="Visibility" Value="Hidden"/>
                            </Trigger>
                        </ControlTemplate.Triggers>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
            <Style.Triggers>
            </Style.Triggers>
        </Style>
        <Style x:Key="{x:Type RadioButton}"
       TargetType="{x:Type RadioButton}">
            <Setter Property="SnapsToDevicePixels"
          Value="true" />
            <Setter Property="OverridesDefaultStyle"
          Value="true" />
            <Setter Property="FocusVisualStyle"
          Value="{DynamicResource RadioButtonFocusVisual}" />
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="{x:Type RadioButton}">
                        <BulletDecorator Background="Transparent">
                            <BulletDecorator.Bullet>
                                <Grid Width="13"
                  Height="13">
                                    <Ellipse x:Name="Border"
                       StrokeThickness="1">
                                        <Ellipse.Stroke>
                                            <LinearGradientBrush EndPoint="0.5,1"
                                       StartPoint="0.5,0">
                                                <GradientStop Color="#FF111111"
                                  Offset="0" />
                                                <GradientStop Color="Black"
                                  Offset="1" />
                                            </LinearGradientBrush>
                                        </Ellipse.Stroke>
                                        <Ellipse.Fill>
                                            <LinearGradientBrush StartPoint="0,0"
                                       EndPoint="0,1">
                                                <LinearGradientBrush.GradientStops>
                                                    <GradientStopCollection>
                                                        <GradientStop Color="#FF303030" />
                                                        <GradientStop Color="#FF222222"
                                      Offset="1.0" />
                                                    </GradientStopCollection>
                                                </LinearGradientBrush.GradientStops>
                                            </LinearGradientBrush>
                                        </Ellipse.Fill>
                                    </Ellipse>
                                    <Ellipse x:Name="CheckMark"
                       Margin="4"
                       Visibility="Collapsed">
                                        <Ellipse.Fill>
                                            <SolidColorBrush Color="#FF555555" />
                                        </Ellipse.Fill>
                                    </Ellipse>
                                </Grid>
                            </BulletDecorator.Bullet>
                            <VisualStateManager.VisualStateGroups>
                                <VisualStateGroup x:Name="CommonStates">
                                    <VisualState x:Name="Normal" />
                                    <VisualState x:Name="MouseOver">
                                        <Storyboard>
                                            <ColorAnimationUsingKeyFrames Storyboard.TargetName="Border"
                                                Storyboard.TargetProperty="(Shape.Fill).
                    (GradientBrush.GradientStops)[1].(GradientStop.Color)">
                                                <EasingColorKeyFrame KeyTime="0"
                                         Value="DarkGray" />
                                            </ColorAnimationUsingKeyFrames>
                                        </Storyboard>
                                    </VisualState>
                                    <VisualState x:Name="Pressed">
                                        <Storyboard>
                                            <ColorAnimationUsingKeyFrames Storyboard.TargetName="Border"
                                                Storyboard.TargetProperty="(Shape.Fill).
                    (GradientBrush.GradientStops)[1].(GradientStop.Color)">
                                                <EasingColorKeyFrame KeyTime="0"
                                         Value="DarkGray" />
                                            </ColorAnimationUsingKeyFrames>
                                        </Storyboard>
                                    </VisualState>
                                    <VisualState x:Name="Disabled">
                                        <Storyboard>
                                            <ColorAnimationUsingKeyFrames Storyboard.TargetName="Border"
                                                Storyboard.TargetProperty="(Shape.Fill).
                    (GradientBrush.GradientStops)[1].(GradientStop.Color)">
                                                <EasingColorKeyFrame KeyTime="0"
                                         Value="DarkGray" />
                                            </ColorAnimationUsingKeyFrames>
                                            <ColorAnimationUsingKeyFrames Storyboard.TargetName="Border"
                                                Storyboard.TargetProperty="(Shape.Stroke).
                    (GradientBrush.GradientStops)[1].(GradientStop.Color)">
                                                <EasingColorKeyFrame KeyTime="0"
                                         Value="#40000000" />
                                            </ColorAnimationUsingKeyFrames>
                                            <ColorAnimationUsingKeyFrames Storyboard.TargetName="Border"
                                                Storyboard.TargetProperty="(Shape.Stroke).
                    (GradientBrush.GradientStops)[0].(GradientStop.Color)">
                                                <EasingColorKeyFrame KeyTime="0"
                                         Value="#40000000" />
                                            </ColorAnimationUsingKeyFrames>
                                        </Storyboard>
                                    </VisualState>
                                </VisualStateGroup>
                                <VisualStateGroup x:Name="CheckStates">
                                    <VisualState x:Name="Checked">
                                        <Storyboard>
                                            <ObjectAnimationUsingKeyFrames Storyboard.TargetProperty="(UIElement.Visibility)"
                                                 Storyboard.TargetName="CheckMark">
                                                <DiscreteObjectKeyFrame KeyTime="0"
                                            Value="{x:Static Visibility.Visible}" />
                                            </ObjectAnimationUsingKeyFrames>
                                        </Storyboard>
                                    </VisualState>
                                    <VisualState x:Name="Unchecked" />
                                    <VisualState x:Name="Indeterminate" />
                                </VisualStateGroup>
                            </VisualStateManager.VisualStateGroups>
                            <ContentPresenter Margin="4,0,0,0"
                            VerticalAlignment="Center"
                            HorizontalAlignment="Left"
                            RecognizesAccessKey="True" />
                        </BulletDecorator>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
        </Style>
    </Window.Resources>
    <Grid>
        <Grid.ColumnDefinitions>
            <ColumnDefinition/>
            <ColumnDefinition/>
            <ColumnDefinition/>
        </Grid.ColumnDefinitions>
        <Grid.RowDefinitions>
            <RowDefinition Height="30"/>
            <RowDefinition/>
            <RowDefinition/>
            <RowDefinition/>
            <RowDefinition/>
            <RowDefinition/>
            <RowDefinition/>
            <RowDefinition/>
        </Grid.RowDefinitions>
        <TextBlock Text="Compute and export EPID QA response"
                   Grid.ColumnSpan="2" Foreground="#FFCCCCCC"/>
        <Button Foreground="#FFCCCCCC" Background="#FF2C2C2C"
                   BorderBrush="#FF2C2C2C" Width="20" Grid.Column="3" HorizontalAlignment="Right"
                   VerticalAlignment="Top" Style="{StaticResource xButton}"
                   Name="CloseButton">
            <Button.Content>
                <TextBlock Text="X" HorizontalAlignment="Center" />
            </Button.Content>
        </Button>
        <TextBlock Text="EPID SID:"
               Margin="5"
               Grid.Row="1"
               Foreground="#FFE2E2E2"/>
        <ComboBox Name="SIDComboBox"
              Margin="5"
              Grid.Column="1"
              Grid.Row="1"
              BorderBrush="#FF2C2C2C"
              Background="#FFCCCCCC"/>
        <StackPanel Orientation="Horizontal"
                Grid.Row="2"
                Grid.Column="0"
                Grid.ColumnSpan="3">
            <RadioButton Content="Use collimator angles from beam set"
                   Margin="5"
                   IsChecked="True" />
            <RadioButton Content="Select collimator angle"
                   Margin="5"
                   Name="SelectCollimatorAngle" />
        </StackPanel>
        <TextBlock Text="Collimator angle [deg]:"
               Margin="5"
               Grid.Column="0"
               Grid.Row="3"
               Visibility="{Binding Path=IsChecked, ElementName=SelectCollimatorAngle, Converter={StaticResource BoolToVisConverter}}"/>
        <TextBox Name="CollimatorAngleTextBox"
             Margin="5"
             Grid.Column="1"
             Grid.Row="3"
             Visibility="{Binding Path=IsChecked, ElementName=SelectCollimatorAngle, Converter={StaticResource BoolToVisConverter}}"
             Style="{StaticResource Textbox}"/>
        <TextBlock Text="Flood field correction:"
               Margin="5"
               Grid.Row="4"
               Foreground="#FFE2E2E2"/>
        <ComboBox Name="FFComboBox"
              Margin="5"
              Grid.Column="1"
              Grid.Row="4"
              BorderBrush="#FF2C2C2C"
              Background="#FFCCCCCC"
              SelectedIndex="0">
            <ComboBoxItem DataContext="{StaticResource BoolToVisConverter}" Content="None" />
            <ComboBoxItem DataContext="{StaticResource BoolToVisConverter}" Content="Match beam energy"/>
            <ComboBoxItem Name="SE" Content="Specify energy"/>
        </ComboBox>
        <TextBlock Text="Flood field energy [MV]:"
               Margin="5"
               Grid.Row="5"
               Foreground="#FFE2E2E2"
               DataContext="{StaticResource BoolToVisConverter}"
               Visibility="{Binding Path=IsSelected, ElementName=SE,  Converter={StaticResource BoolToVisConverter}}"/>
        <ComboBox Name="FFEComboBox"
              Margin="5"
              Grid.Column="1"
              Grid.Row="5"
              BorderBrush="#FF2C2C2C"
              Background="#FFCCCCCC"
              DataContext="{StaticResource BoolToVisConverter}"
              Visibility="{Binding Path=IsSelected, ElementName=SE,  Converter={StaticResource BoolToVisConverter}}"/>
        <TextBlock Text="Export path:"
               Margin="5"
               Grid.Column="0"
               Grid.Row="6"/>
        <ComboBox Name="ExportPathComboBox"
              Margin="5"
              Grid.Column="1"
              Grid.Row="6"
              BorderBrush="#FF2C2C2C"
              Background="#FFCCCCCC"/>
        <Button Name="BrowseButton"
            Content="Browse..."
            Grid.Column="2"
            Grid.Row="6"
            Margin="5"
            Width="70"
            Style="{StaticResource CancelRoundCorner}"/>
        <Button Name="SaveDefaultButton"
            Content="Save Default"
            IsEnabled="False"
            Grid.Column="0"
            Grid.Row="7"
            Margin="5"
            Width="86"
            Style="{StaticResource DefaultRoundCorner}"/>
        <Button Grid.Row="7"
            Grid.ColumnSpan="3"
            Content="Run"
            Width="70"
            HorizontalAlignment="Center"
            Margin="5"
            Name="RunButton"
            Style="{StaticResource OKRoundCorner}"/>
    </Grid>
</Window>
    """

xr = XmlReader.Create(StringReader(xaml))

run_epid_qa_automatic()
