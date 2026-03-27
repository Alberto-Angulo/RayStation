from datetime import datetime
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.uid import generate_uid
from scipy.interpolate import RegularGridInterpolator
import numpy as np

def compute_epid_qa_response(patient, plan, beam_set, grid_resolution, phantom_name, phantom_id,
                             collimator_angle, sid, isocenter, detector_plane_y, machine_sad, ui,
                             dicom_save_folder, apply_flood_field, single_flood_field_beam_quality_id):

    epid_response_options = {
        'PhantomName': phantom_name,
        'PhantomId': phantom_id,
        'DoseGrid': grid_resolution,
        'GantryAngle': 0,
        'CouchRotationAngle': 0,
        'ApplyFloodFieldCorrection': apply_flood_field,
        'SingleFloodFieldBeamQualityId': single_flood_field_beam_quality_id,
        'FloodFieldFactor': 0.5}

    if collimator_angle != '': epid_response_options['CollimatorAngle'] = collimator_angle
    epid_response_options['IsoCenter'] = isocenter
    epid_response_options['QAPlanName'] = get_unique_qa_plan_name(plan,'EPID QA')
    try:
        beam_set.CreateEPIDResponse(**epid_response_options)
    except Exception as e:
        raise Exception('QA Plan creation is not possible, please review the following critical error:\n{}'.format(e))

    epid_qa_plan = plan.VerificationPlans[plan.VerificationPlans.Count-1]
    dose_grid = epid_qa_plan.BeamSet.FractionDose.InDoseGrid
    dose_planes = get_interpolated_dose(isocenter, detector_plane_y, dose_grid, epid_qa_plan.BeamSet.FractionDose.BeamDoses)
    print("Computation completed")
    print("Export to DICOM RTImage")
    dicom_files = prepare_dicom_files(patient, beam_set, collimator_angle, sid, grid_resolution, machine_sad, ui)
    export_dicom(patient.Name, plan.Name,  beam_set, dicom_save_folder,dicom_files, dose_planes)



def get_unique_qa_plan_name(plan, qa_base_name):
    """
    Checks the current names of QA plans in the current treatment plan and increases the name count to be unique
    :param qa_base_name: base name of the QA plan, must be less than 13 characters and ideally less than 10
    :return:
    qa_plan_name: unique qa plan name
    """
    if len(qa_base_name) > 13:
        raise Exception('The base plan name for the QA plan is too long, please keep try to keep it under 10 chars')
    i = 2
    qa_plan_name = '{} {}'.format(qa_base_name, 1)
    current_qa_plan_names = [qa_plan.BeamSet.DicomPlanLabel for qa_plan in plan.VerificationPlans]
    while qa_plan_name in current_qa_plan_names:
        qa_plan_name = '{} {}'.format(qa_base_name, i)
        i += 1
    if len(qa_plan_name) > 16:
        raise Exception('The base plan name for the QA plan is too long or there are too many QA Plans,' 
                        'the length of the  QA plan name exceeds 16 characters.')
    return qa_plan_name

def get_interpolated_dose(isocenter, detector_plane_y, dosegrid, doses):
    """
    gets the interpolated dose at the desired plane. Uses RegularGridInterpolator from scipy to linearly interpolate
    between neighbouring values. Takes an array of points and returns an array of interpolated points.
    :param dosegrid: handle to the dose grid for the phantom
    :param doses: numpy array of corrected grid doses, array index corresponds to the beam index
    :return:
    dose_planes: numpy array of 2D flattened array for the interpolated dose plane,
        array index corresponds to beam index
    """
    global dimens
    dimens = doses[0].DoseValues.DoseData.shape
    dose_planes = np.array(np.zeros(len(doses)), object)
    voxel_center_xmin = dosegrid.Corner.x + dosegrid.VoxelSize.x / 2
    voxel_center_ymin = dosegrid.Corner.y + dosegrid.VoxelSize.y / 2
    voxel_center_zmin = dosegrid.Corner.z + dosegrid.VoxelSize.z / 2
    voxel_center_xmax = voxel_center_xmin + (dosegrid.NrVoxels.x-1) * dosegrid.VoxelSize.x
    voxel_center_ymax = voxel_center_ymin + (dosegrid.NrVoxels.y-1) * dosegrid.VoxelSize.y 
    voxel_center_zmax = voxel_center_zmin + (dosegrid.NrVoxels.z-1) * dosegrid.VoxelSize.z
    xlin = np.linspace(voxel_center_xmin, voxel_center_xmax, dosegrid.NrVoxels.x)
    ylin = np.linspace(voxel_center_ymin, voxel_center_ymax, dosegrid.NrVoxels.y)
    zlin = np.linspace(voxel_center_zmin, voxel_center_zmax, dosegrid.NrVoxels.z)

    my_grid = []
    for z in np.flipud(zlin):
        for x in xlin:
            my_grid.append([z, detector_plane_y, x])

    for i, dose in enumerate(doses):
        my_interp_function = RegularGridInterpolator((zlin, ylin, xlin), dose.DoseValues.DoseData)
        dose_planes[i] = my_interp_function(my_grid)

    return dose_planes


def prepare_dicom_files(patient, beam_set, collimator_angle, sid, grid_resolution, machine_sad, ui):
    """
    creates pydicom RTImage objects for each beam dose
    :return:
    pydicom_files: List: RTImage object, index corresponds to beam index
    """
    pydicom_files = []
    frame_of_reference = beam_set.FrameOfReference
    for beam in beam_set.Beams:
        this_collimator_angle = collimator_angle if collimator_angle != '' else beam.Segments[0].CollimatorAngle
        now = datetime.now()
        
        patient_position = beam_set.PatientPosition
        if 'Head' in patient_position:
            patient_position = 'HFS' if 'Supine' in patient_position else 'HFP'
        else:
            patient_position = 'FFS' if 'Supine' in patient_position else 'FFP'

        # File meta info data elements
        file_meta = Dataset()
        file_meta.FileMetaInformationGroupLength = 188
        file_meta.FileMetaInformationVersion = b'\x00\x01'
        file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.481.1'
        file_meta.MediaStorageSOPInstanceUID = '1.2.246.352.221.47782988025790138949850682079388322961'
        file_meta.TransferSyntaxUID = '1.2.840.10008.1.2'
        file_meta.ImplementationClassUID = '1.2.246.352.70.2.1.160.3'
        file_meta.ImplementationVersionName = 'DCIE 2.2'

        # Main data elements
        ds = Dataset()
        ds.SpecificCharacterSet = 'ISO_IR 192'
        ds.InstanceCreationDate = now.strftime('%Y%m%d')
        ds.InstanceCreationTime = now.strftime('%H%M%S')
        ds.SOPClassUID = '1.2.840.10008.5.1.4.1.1.481.1'
        ds.SOPInstanceUID = generate_uid()
        ds.StudyDate = ''
        ds.ContentDate = ''
        ds.StudyTime = ''
        ds.ContentTime = ''
        ds.AccessionNumber = ''
        ds.Modality = 'RTIMAGE'
        ds.ConversionType = 'DI'
        ds.Manufacturer = 'RaySearch Laboratories'
        ds.ReferringPhysicianName = ''
        ds.OperatorsName = ''
        ds.ManufacturerModelName = 'RayStation'
        ds.PatientName = patient.Name
        ds.PatientID = patient.PatientID
        ds.PatientIdentityRemoved = 'NO'

        ds.SoftwareVersions = ui.GetApplicationVersion()
        ds.PatientPosition = patient_position
        ds.StudyInstanceUID = generate_uid()
        ds.SeriesInstanceUID = generate_uid()
        ds.StudyID = ''
        ds.SeriesNumber = "0"
        ds.InstanceNumber = None
        ds.PatientOrientation = ''
        ds.FrameOfReferenceUID = frame_of_reference
        ds.PositionReferenceIndicator = ''
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = 'MONOCHROME1'
        ds.Rows = dimens[0]
        ds.Columns = dimens[2]
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 0
        ds.LongitudinalTemporalInformationModified = 'REMOVED'
        ds.WindowCenter = "32768"
        ds.WindowWidth = "65535"
        ds.RescaleIntercept = "0.0"
        ds.RescaleSlope = "1.0"
        ds.RescaleType = 'Gy'
        ds.RTImageLabel = beam.Name
        ds.RTImageDescription = '{} MV, Exported From RayStation, Flood Field Correction Applied'.format(beam.BeamQualityId)
        ds.ReportedValuesOrigin = 'ACTUAL'
        ds.RTImagePlane = 'NORMAL'
        ds.XRayImageReceptorTranslation = [0.3623617, 0.7317194, 0]
        ds.XRayImageReceptorAngle = "0.0"
        ds.ImagePlanePixelSpacing = [grid_resolution['x'] * 10, grid_resolution['z'] * 10]
        ds.RTImagePosition = [-249.9998, 230.4807]
        ds.RadiationMachineName = beam_set.MachineReference.MachineName
        ds.RadiationMachineSAD = machine_sad*10
        ds.RTImageSID = str(sid)
        ds.FractionNumber = "1"
        ds.ImageType="ORIGINAL\PRIMARY\PORTAL\PREDICTED_DOSE"

        # Exposure Sequence
        exposure_sequence = Sequence()
        ds.ExposureSequence = exposure_sequence

        # Exposure Sequence: Exposure 1
        exposure1 = Dataset()
        exposure1.ReferencedFrameNumber = "1"
        exposure1.KVP = str(int(beam.BeamQualityId.split()[0]) * 1000)
        exposure1.MetersetExposure = f'{beam.BeamMU:.10f}'

        # Beam Limiting Device Sequence
        beam_limiting_device_sequence = Sequence()
        exposure1.BeamLimitingDeviceSequence = beam_limiting_device_sequence

        # Beam Limiting Device Sequence: Beam Limiting Device 1
        beam_limiting_device1 = Dataset()
        beam_limiting_device1.RTBeamLimitingDeviceType = 'ASYMX'
        beam_limiting_device1.NumberOfLeafJawPairs = "1"
        beam_limiting_device1.LeafJawPositions = [-100, 100]
        beam_limiting_device_sequence.append(beam_limiting_device1)

        # Beam Limiting Device Sequence: Beam Limiting Device 2
        beam_limiting_device2 = Dataset()
        beam_limiting_device2.RTBeamLimitingDeviceType = 'Y'
        beam_limiting_device2.NumberOfLeafJawPairs = "1"
        beam_limiting_device2.LeafJawPositions = [-100, 100]
        beam_limiting_device_sequence.append(beam_limiting_device2)

        exposure1.NumberOfBlocks = "0"
        exposure1.GantryAngle = "0"
        exposure1.BeamLimitingDeviceAngle = f'{this_collimator_angle:.12f}'
        exposure1.PatientSupportAngle = "0.0"
        exposure_sequence.append(exposure1)

        ds.PrimaryDosimeterUnit = 'MU'
        ds.GantryAngle = "0.0"
        ds.BeamLimitingDeviceAngle = f'{this_collimator_angle:.12f}'
        ds.PatientSupportAngle = "0.0"
        ds.TableTopVerticalPosition = "0.0"
        ds.TableTopLongitudinalPosition = "0.0"
        ds.TableTopLateralPosition = "0.0"
        ds.IsocenterPosition = [0, 0, 0]

        # Referenced RT Plan Sequence
        refd_rt_plan_sequence = Sequence()
        ds.ReferencedRTPlanSequence = refd_rt_plan_sequence

        # Referenced RT Plan Sequence: Referenced RT Plan 1
        refd_rt_plan1 = Dataset()
        refd_rt_plan1.ReferencedSOPClassUID = '1.2.840.10008.5.1.4.1.1.481.5'
        refd_rt_plan1.ReferencedSOPInstanceUID = beam_set.ModificationInfo.DicomUID 
        refd_rt_plan_sequence.append(refd_rt_plan1)

        ds.ReferencedBeamNumber = beam.Number
        ds.ReferencedFractionGroupNumber = "1"
        ds.PixelData = None

        ds.file_meta = file_meta
        ds.is_implicit_VR = True
        ds.is_little_endian = True
        pydicom_files.append(ds)
    return pydicom_files


def export_dicom(patient_name, plan_name, beam_set, dicom_save_folder, dicom_files, planar_doses):
    """
    Exports the RTImage objects to files. Formats the dose as RTImage pixel data.
    :param dicom_files: List: RTImage object, index corresponds to beam index
    :param planar_doses: numpy array of 2D flattened array for the interpolated dose plane,
        array index corresponds to beam index
    :return: None
    """
    for i, dose_file in enumerate(dicom_files):
        file_name = 'EPID_RS_{}_{}_{}_{}'.format(patient_name, plan_name, beam_set.DicomPlanLabel, beam_set.Beams[i].Name)
        max_dose = np.max(planar_doses[i])

        #for x in np.nditer(planar_doses[i], op_flags=['readwrite']):
        #    x[...] = (16384 - x/max_dose * 16384)
        #    #x[...] = (x/max_dose * 16384)
        
        pixel_data = (planar_doses[i] / max_dose * 65535).astype(np.uint16)
        dose_file.PixelData = pixel_data.tobytes()
        
        #dose_file.PixelData = planar_doses[i].astype(np.uint16).tostring()
        dose_file.save_as('{}\\{}.dcm'.format(dicom_save_folder, file_name), write_like_original=False)
        
       