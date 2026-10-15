"""Contract checks for released byte totals, notes, colour rule and DCT masking."""
import io,json,shutil,subprocess,sys,unittest
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import verify_plan_scope
from image_notes import validate_notes_rows,mask_rectangles
from green_pixel_fraction import vegetation_mask,region_mask,in_window,daily_rows
from apply_head_masks import wipe_jpeg

class ReleaseContracts(unittest.TestCase):
 def setUp(self):
  self.public=[{'release_id':'QUI_GH1_20230530_0001','camera_id':'GH-1','file_size_bytes':'250'}, {'release_id':'QUI_GH2_20230531_0001','camera_id':'GH-2','file_size_bytes':'500'}]
  self.plan={'image_scope':{'total_images':2,'camera_counts':{'GH-1':1,'GH-2':1},'logical_jpeg_bytes':750}}
  self.note={'release_id':self.public[1]['release_id'],'note_type':'person_masked','box_or_description':'[[16,16,48,48]]'}
 def test_new_logical_total_is_accepted(self):self.assertEqual(verify_plan_scope(self.public,self.plan),750)
 def test_wrong_total_is_rejected(self):
  self.plan['image_scope']['logical_jpeg_bytes']=751
  with self.assertRaises(ValueError):verify_plan_scope(self.public,self.plan)
 def test_changed_camera_scope_is_rejected(self):
  self.plan['image_scope']['camera_counts']={'GH-1':2}
  with self.assertRaises(ValueError):verify_plan_scope(self.public,self.plan)
 def test_notes_preserve_exact_rectangles(self):
  summary,masks=validate_notes_rows([self.note],self.public)
  self.assertEqual(summary['masked_frames'],1);self.assertEqual(masks[self.note['release_id']],[[16,16,48,48]])
 def test_duplicate_note_rejected(self):
  with self.assertRaises(ValueError):validate_notes_rows([self.note,self.note],self.public)
 def test_unknown_note_id_and_type_rejected(self):
  for key,value in [('release_id','unknown'),('note_type','no_head_keep')]:
   with self.subTest(key=key),self.assertRaises(ValueError):validate_notes_rows([{**self.note,key:value}],self.public)
 def test_bad_mask_geometry_rejected(self):
  for box in [[15,16,48,48],[16,16,16,48],[0,0,2576,48],[1600,1344,1616,1360],[16.0,16,48,48],[True,16,48,48]]:
   with self.subTest(box=box),self.assertRaises(ValueError):mask_rectangles(json.dumps([box]))
 def test_empty_mask_and_description_rejected(self):
  with self.assertRaises(ValueError):mask_rectangles('[]')
  with self.assertRaises(ValueError):validate_notes_rows([{**self.note,'note_type':'exposure_anomaly','box_or_description':' '}],self.public)
 def test_changed_unmasked_size_rejected(self):
  images=[{**r,'original_file_size_bytes':r['file_size_bytes']} for r in self.public];images[0]['original_file_size_bytes']='300'
  with self.assertRaises(ValueError):validate_notes_rows([self.note],self.public,images)
 def test_plan_note_count_checked(self):
  self.plan['image_masking']={'masked_frames':2,'camera_counts':{'GH-1':0,'GH-2':2}}
  with self.assertRaises(ValueError):validate_notes_rows([self.note],self.public,plan=self.plan)
 def test_colour_rule_strict_thresholds_and_no_uint_overflow(self):
  rgb=np.array([[[94,100,80],[95,100,80],[80,100,95],[90,100,90],[89,100,90],[0,0,0],[230,250,230]]],dtype=np.uint8)
  self.assertEqual(vegetation_mask(rgb).tolist(),[[True,False,False,False,True,False,True]])
 def test_frozen_region_pixels(self):
  region=json.loads((Path(__file__).resolve().parents[1]/'resources/green_fraction_region.json').read_text());self.assertEqual(int(region_mask(region).sum()),659928)
 def test_endpoint_seconds_do_not_drop_frame(self):
  self.assertTrue(in_window('2023-06-01T15:00:03'));self.assertTrue(in_window('2023-06-01T18:00:59'));self.assertFalse(in_window('2023-06-01T14:59:59'));self.assertFalse(in_window('2023-06-01T18:01:00'))
 def test_daily_median(self):
  rows=[{'timestamp':'2023-06-01T15:00:02','green_fraction':.2},{'timestamp':'2023-06-01T15:10:02','green_fraction':.8}]
  self.assertEqual(daily_rows(rows),[{'date':'2023-06-01','green_fraction':.5,'frames':2}])
 @unittest.skipUnless(shutil.which('jpegtran'),'jpegtran is required for the DCT contract test')
 def test_mask_preserves_every_outside_DCT_region(self):
  y,x=np.mgrid[:64,:64];arr=np.stack([(x*3+y)%256,(y*4+x)%256,(x*2+y*2)%256],axis=-1).astype(np.uint8)
  data=io.BytesIO();Image.fromarray(arr).save(data,format='JPEG',quality=95,subsampling=2);original=data.getvalue();masked=wipe_jpeg(original,[[16,16,32,32]])
  def crop(blob,geometry):return subprocess.run(['jpegtran','-copy','none','-optimize','-crop',geometry],input=blob,capture_output=True,check=True).stdout
  for geometry in ['16x64+0+0','48x16+16+0','32x48+32+16','16x32+16+32']:self.assertEqual(crop(original,geometry),crop(masked,geometry))
  with Image.open(io.BytesIO(crop(masked,'16x16+16+16'))) as im:self.assertTrue(np.all(np.asarray(im.convert('RGB'))==128))
if __name__=='__main__':unittest.main()
