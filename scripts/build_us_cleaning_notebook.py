"""Build the self-contained cleaning notebook. Execute the notebook to clean data."""
from pathlib import Path
import nbformat as nbf

PROJECT = Path(__file__).resolve().parents[1]
cells = []

def md(text):
    cells.append(nbf.v4.new_markdown_cell(text.strip()))

def code(text):
    compile(text.strip(), '<notebook cell>', 'exec')
    cells.append(nbf.v4.new_code_cell(text.strip()))

md('''
# 02 美国事故数据清洗与分表

本 notebook 只清洗数据、生成可连接的实验输入表及质量报告。全国数据统一处理，洛杉矶按原表城市标签单独导出。尚未确定正式边界、网格尺度或时间切分，因此在这里保留事件粒度。

请从头运行全部单元格，在 Python 3.11 环境安装 requirements.txt 并选择对应内核。需要 pandas、numpy、pyarrow、duckdb、nbformat、nbclient 和 ipykernel。DuckDB 分批处理并使用项目内临时磁盘，避免把七百多万条记录一次装入 pandas。项目路径根据 notebook 的工作目录自动识别。

每次运行写入 `cleaned_data/run_时间_随机后缀/`。成功验收后才更新 `cleaned_data/LATEST_RUN.txt`；失败运行保留 RUNNING 标记供排查。原始文件只读，各表均保留事故 ID。
''')
code(r"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import sys
import uuid
import importlib.metadata
import duckdb
import pandas as pd
import pyarrow.parquet as pq

assert sys.version_info >= (3, 11), '请使用 Python 3.11 或更新版本'
PROJECT = next((p for p in (Path.cwd().resolve(), *Path.cwd().resolve().parents)
                if (p / 'data').is_dir() and (p / 'notebooks').is_dir()
                and (p / 'requirements.txt').is_file()), None)
if PROJECT is None:
    raise RuntimeError('请从项目根目录或 notebooks 目录启动 notebook')
DATA = PROJECT / 'data'
files = sorted(DATA.glob('train-*-of-*.parquet'))
assert len(files) == 7, '检查是否完整下载七个原始分片'
root = PROJECT / 'cleaned_data'
run_id = 'run_' + datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
RUN = root / run_id
for folder in ['01_national', '02_los_angeles', '03_text', '04_quality', '05_metadata', '_work']:
    (RUN / folder).mkdir(parents=True, exist_ok=False)
(RUN / 'RUNNING').write_text('运行完成并校验后才发布。', encoding='utf-8')
def sql_string(value):
    return "'" + str(value).replace("'", "''") + "'"
def qi(value):
    return '"' + value.replace('"', '""') + '"'
con = duckdb.connect(str(RUN / '_work' / 'cleaning.duckdb'))
con.execute("SET memory_limit='1500MB'")
con.execute('SET threads=2')
con.execute('SET preserve_insertion_order=false')
con.execute('SET temp_directory=' + sql_string((RUN / '_work' / 'spill').as_posix()))
print('解释器', sys.executable)
print('输出目录', RUN)
""")
md('''
## 1 文件与列名检查

计算原文件 SHA-256，核对七个分片的 schema。主表列名统一为 snake_case，并在字段映射中保留原名与单位。数字单位保留英制，避免无意混用公里、英里、华氏度与摄氏度。时间保留当地墙上时间和独立时区列，尚未转换 UTC。
''')
code(r"""
# 原名、清洗名、语义类别
mapping = [
('ID','event_id','标识'),('Source','source','来源'),('Severity','severity','交通影响等级'),
('Start_Time','start_time_local','当地时间'),('End_Time','end_time_local','当地时间'),
('Start_Lat','start_lat','纬度'),('Start_Lng','start_lng','经度'),
('End_Lat','end_lat','纬度'),('End_Lng','end_lng','经度'),
('Distance(mi)','distance_mi','英里'),('Description','description','历史事件文本'),
('Street','street','地址'),('City','city','地址'),('County','county','地址'),
('State','state','州'),('Zipcode','zipcode','邮编字符串'),('Country','country','国家'),
('Timezone','timezone','时区'),('Airport_Code','airport_code','天气站'),
('Weather_Timestamp','weather_time_local','当地天气观测时间'),
('Temperature(F)','temperature_f','华氏度'),('Wind_Chill(F)','wind_chill_f','华氏度'),
('Humidity(%)','humidity_pct','百分比'),('Pressure(in)','pressure_in','英寸汞柱'),
('Visibility(mi)','visibility_mi','英里'),('Wind_Direction','wind_direction','类别'),
('Wind_Speed(mph)','wind_speed_mph','英里每小时'),('Precipitation(in)','precipitation_in','英寸'),
('Weather_Condition','weather_condition','类别'),('Amenity','amenity','附近设施标记'),
('Bump','bump','附近设施标记'),('Crossing','crossing','附近设施标记'),
('Give_Way','give_way','附近设施标记'),('Junction','junction','附近设施标记'),
('No_Exit','no_exit','附近设施标记'),('Railway','railway','附近设施标记'),
('Roundabout','roundabout','附近设施标记'),('Station','station','附近设施标记'),
('Stop','stop','附近设施标记'),('Traffic_Calming','traffic_calming','附近设施标记'),
('Traffic_Signal','traffic_signal','附近设施标记'),('Turning_Loop','turning_loop','附近设施标记'),
('Sunrise_Sunset','sunrise_sunset','昼夜类别'),('Civil_Twilight','civil_twilight','昼夜类别'),
('Nautical_Twilight','nautical_twilight','昼夜类别'),
('Astronomical_Twilight','astronomical_twilight','昼夜类别')]
schema = pq.ParquetFile(files[0]).schema_arrow
assert schema.names == [r[0] for r in mapping]
manifest = []
for path in files:
    parquet = pq.ParquetFile(path)
    assert parquet.schema_arrow.equals(schema)
    with path.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    manifest.append(dict(file=path.name, bytes=path.stat().st_size,
                         rows=parquet.metadata.num_rows, sha256=digest))
pd.DataFrame(manifest).to_csv(RUN / '05_metadata/source_files.csv', index=False, encoding='utf-8-sig')
field_map = pd.DataFrame(mapping, columns=['source_column','clean_column','meaning_or_unit'])
field_map['source_type'] = [str(f.type) for f in schema]
field_map.to_csv(RUN / '05_metadata/field_mapping.csv', index=False, encoding='utf-8-sig')
file_sql = '[' + ','.join(sql_string(p.as_posix()) for p in files) + ']'
con.execute(f'''CREATE VIEW raw AS SELECT * FROM read_parquet(
    {file_sql}, filename=true, file_row_number=true, hive_partitioning=false)''')
raw_count = sum(row['rows'] for row in manifest)
display(pd.DataFrame(manifest)[['file','rows','bytes']])
print('全国原始记录', raw_count)
""")
md('''
## 2 去重及隔离规则

- ID 去除两端空白，空字符串视为空值。ID 空缺的记录单独隔离。
- 同一 ID 的 46 个原始字段完全一致时只保留一条，按源文件名及零基行号确定保留顺序。重复副本的来源单独保存。
- 同一 ID 的内容不一致时全部隔离，避免擅自选择哪个版本真实。不同 ID 即使时间与位置相同也保留，后面另列待核查组。
- 缺失或无法解析的开始时间，以及起点坐标不有限或超出全球经纬度范围的记录，进入隔离表。州/城市/天气/文本缺失不触发事故记录删除。

以上规则检查数据可用性，具体城市范围由下一步城市筛选界定。
''')
code(r"""
con.execute('''CREATE TABLE duplicate_ids AS
 SELECT nullif(trim(ID),'') AS event_id, count(*) AS row_count
 FROM raw WHERE nullif(trim(ID),'') IS NOT NULL
 GROUP BY 1 HAVING count(*) > 1''')
# 只对重复 ID 比较完整原始行，不对全国所有文本排序。
raw_fields = ', '.join(qi(a) for a, _, _ in mapping)
con.execute(f'''CREATE TABLE duplicate_variants AS
 SELECT nullif(trim(ID),'') event_id, count(*) variants FROM (
   SELECT DISTINCT {raw_fields} FROM raw
   WHERE nullif(trim(ID),'') IN (SELECT event_id FROM duplicate_ids)
 ) GROUP BY 1''')
con.execute('''CREATE TABLE conflict_ids AS
 SELECT event_id FROM duplicate_variants WHERE variants > 1''')
con.execute('''CREATE TABLE redundant_copies AS
 SELECT filename, file_row_number, event_id FROM (
   SELECT filename, file_row_number, nullif(trim(ID),'') event_id,
     row_number() OVER (PARTITION BY nullif(trim(ID),'') ORDER BY filename, file_row_number) duplicate_rank
   FROM raw WHERE nullif(trim(ID),'') IN (
     SELECT event_id FROM duplicate_variants WHERE variants = 1)
 ) WHERE duplicate_rank > 1''')
expressions = []
for original, clean, _ in mapping:
    expr = qi(original)
    if str(schema.field(original).type) == 'string':
        expr = f"nullif(trim({expr}), '')"
    if clean in ['state','country']:
        expr = f'upper({expr})'
    if clean in ['start_time_local','end_time_local','weather_time_local']:
        expr = f'TRY_CAST({expr} AS TIMESTAMP)'
    expressions.append(f'{expr} AS {qi(clean)}')
con.execute(f'''CREATE TABLE normalized AS SELECT
 {', '.join(expressions)}, Start_Time AS raw_start_time, End_Time AS raw_end_time,
 Weather_Timestamp AS raw_weather_time, regexp_extract(filename, '[^/\\\\]+$') AS source_file,
 file_row_number AS source_row_number,
 nullif(trim(ID),'') IN (SELECT event_id FROM conflict_ids) AS id_conflict,
 EXISTS (SELECT 1 FROM redundant_copies d WHERE d.filename=raw.filename
         AND d.file_row_number=raw.file_row_number) AS redundant_copy
 FROM raw''')
con.execute('''CREATE TABLE classified AS SELECT *, CASE
 WHEN event_id IS NULL THEN 'missing_id'
 WHEN id_conflict THEN 'conflicting_id'
 WHEN redundant_copy THEN 'exact_duplicate_copy'
 WHEN start_time_local IS NULL THEN 'invalid_start_time'
 WHEN NOT coalesce(isfinite(start_lat) AND isfinite(start_lng)
     AND start_lat BETWEEN -90 AND 90 AND start_lng BETWEEN -180 AND 180, false)
 THEN 'invalid_start_coordinate'
 ELSE 'kept' END AS disposition FROM normalized''')
audit = con.execute('SELECT disposition,count(*) rows FROM classified GROUP BY 1 ORDER BY 1').df()
assert audit['rows'].sum() == raw_count
audit.to_csv(RUN / '04_quality/row_disposition.csv', index=False, encoding='utf-8-sig')
display(audit)
""")
md('''
## 3 可选字段的保守清洗

只把数学或物理定义上明显无效的数值设为空。湿度须在 0–100，气压须大于 0，能见度、风速、降水、影响路段长度须非负；所有数值需有限。原始数值保留在 `_raw` 列，另列 `_invalid` 与 `_missing` 标记。气温和风寒温度允许负数，只处理非有限值；高但非负的极端数值留给后续训练期核查。

终点或结束时间异常不影响开始事件计数。负时长标记，不用时长预测未来。空白文本变为空值，其他文本保持内容。设施 False 与缺失分别保留。显式缺失标记为布尔变量。

天气观测时间可能晚于事故开始时间，这是可观测性问题。保留有符号时间差；后续按预测周一检查观测时间，不能仅凭事故日期认定所有附加信息当时已知。结束时间也不证明通报最终版本何时发布。
''')
code(r"""
numeric_rules = {
 'distance_mi':'distance_mi >= 0', 'temperature_f':'true', 'wind_chill_f':'true',
 'humidity_pct':'humidity_pct BETWEEN 0 AND 100', 'pressure_in':'pressure_in > 0',
 'visibility_mi':'visibility_mi >= 0', 'wind_speed_mph':'wind_speed_mph >= 0',
 'precipitation_in':'precipitation_in >= 0'}
numeric_clean = []
for col, rule in numeric_rules.items():
    valid = f'(isfinite({col}) AND ({rule}))'
    numeric_clean.extend([f'{col} AS {col}_raw', f'CASE WHEN {valid} THEN {col} END AS {col}',
                          f'({col} IS NOT NULL AND NOT coalesce({valid},false)) AS {col}_invalid'])
removed = list(numeric_rules) + ['severity','end_lat','end_lng','id_conflict','redundant_copy','disposition']
con.execute(f'''CREATE TABLE clean_values AS SELECT * EXCLUDE ({','.join(removed)}),
 {', '.join(numeric_clean)}, severity AS severity_raw,
 CASE WHEN severity BETWEEN 1 AND 4 THEN severity END AS severity,
 (severity IS NOT NULL AND severity NOT BETWEEN 1 AND 4) AS severity_invalid,
 end_lat AS end_lat_raw, end_lng AS end_lng_raw,
 CASE WHEN isfinite(end_lat) AND end_lat BETWEEN -90 AND 90 THEN end_lat END AS end_lat,
 CASE WHEN isfinite(end_lng) AND end_lng BETWEEN -180 AND 180 THEN end_lng END AS end_lng,
 (end_lat IS NOT NULL AND NOT coalesce(isfinite(end_lat) AND end_lat BETWEEN -90 AND 90,false))
 OR (end_lng IS NOT NULL AND NOT coalesce(isfinite(end_lng) AND end_lng BETWEEN -180 AND 180,false)) AS end_coordinate_invalid
 FROM classified WHERE disposition='kept' ''')
flag_fields = list(numeric_rules) + ['end_lat','end_lng','weather_time_local','weather_condition',
 'description','city','state','timezone','severity'] + [b for _, b, g in mapping if g=='附近设施标记']
missing_flags = ','.join(f'{c} IS NULL AS {c}_missing' for c in flag_fields)
con.execute(f'''CREATE TABLE clean AS SELECT *, {missing_flags},
 date_trunc('week',start_time_local)::DATE AS week_start_local,
 year(start_time_local)::INTEGER AS event_year,
 CASE WHEN regexp_full_match(coalesce(state,''),'[A-Z]{{2}}') THEN state ELSE 'UNKNOWN' END AS state_partition,
 coalesce(lower(city)='los angeles' AND state='CA',false) AS is_los_angeles_city_label,
 coalesce(timezone IN ('US/Eastern','US/Central','US/Mountain','US/Pacific','US/Alaska','US/Hawaii'),false) AS timezone_recognized,
 (raw_end_time IS NOT NULL AND trim(raw_end_time)<>'' AND end_time_local IS NULL) AS end_time_parse_failed,
 (raw_weather_time IS NOT NULL AND trim(raw_weather_time)<>'' AND weather_time_local IS NULL) AS weather_time_parse_failed,
 coalesce(end_time_local < start_time_local,false) AS end_before_start,
 epoch(weather_time_local-start_time_local)/60.0 AS weather_lag_minutes,
 CASE WHEN weather_time_local IS NULL THEN NULL ELSE weather_time_local>start_time_local END AS weather_after_start,
 CASE WHEN end_time_local>=start_time_local THEN epoch(end_time_local-start_time_local)/60.0 END AS recorded_impact_minutes,
 CASE WHEN end_time_local IS NULL THEN 'unknown' WHEN end_time_local<start_time_local THEN 'invalid_end_before_start' WHEN end_time_local<=date_trunc('week',start_time_local)+INTERVAL 7 DAY
 THEN 'ended_within_start_week' ELSE 'continues_beyond_start_week' END AS end_relative_to_start_week,
 'unverified'::VARCHAR AS description_asof_status
 FROM clean_values''')
counts = con.execute('''SELECT count(*) kept, sum(is_los_angeles_city_label) la,
 min(start_time_local) first_start, max(start_time_local) last_start FROM clean''').df()
display(counts)
""")
md('''
## 4 分类导出及使用方式

全国主表按州分区，包含全部清洗列、来源及质量标记。洛杉矶按原表 City 标签匹配，尚未使用正式行政边界。

- `02_los_angeles/events_core.parquet` 提供事件时间、坐标和来源，用于后续边界裁剪、网格与计数。含真实事故点，不含补零样本或训练标签。
- `02_los_angeles/environment.parquet` 保留同一批事件 ID 的环境列、缺失标记和天气观测时间。按 event_id 一对一连接，缺失天气的事件仍存在。
- `03_text/los_angeles_text_events.parquet` 保留全部洛杉矶事件及文本可用性；`los_angeles_text_candidates.parquet` 是非空文本候选，尚未做 StartLux 推理。
- `03_text/unique_texts.parquet` 保存去除两端空白后完全相同文本的复用键和使用次数，可用于后续一次提取、多事件复用。每条事件仍独立保留。

数据清洗阶段保持缺失值，不拟合填补器、缩放器、独热编码或特征阈值。这些步骤应在未来训练期拟合。低能见度阈值、周历史窗口以及城市正式边界由后续实验确定。
''')
code(r"""
def export_query(query, path, partition=None):
    options = "FORMAT PARQUET, COMPRESSION ZSTD"
    if partition:
        options += f', PARTITION_BY ({partition}), WRITE_PARTITION_COLUMNS true'
    con.execute(f'COPY ({query}) TO {sql_string(path.as_posix())} ({options})')

export_query('SELECT * FROM clean', RUN / '01_national' / 'events', 'state_partition')
export_query("SELECT * FROM classified WHERE disposition NOT IN ('kept','exact_duplicate_copy')",
             RUN / '04_quality/quarantined_events.parquet')
export_query("SELECT event_id,source_file,source_row_number FROM classified WHERE disposition='exact_duplicate_copy'",
             RUN / '04_quality/removed_duplicate_copies.parquet')
con.execute('CREATE VIEW la AS SELECT * FROM clean WHERE is_los_angeles_city_label')
core_cols = ['event_id','source','start_time_local','week_start_local','event_year',
 'start_lat','start_lng','street','city','county','state','zipcode','country','timezone',
 'timezone_recognized','source_file','source_row_number']
export_query('SELECT '+','.join(core_cols)+' FROM la', RUN / '02_los_angeles/events_core.parquet')
env_cols = ['event_id','start_time_local','weather_time_local','raw_weather_time','weather_lag_minutes',
 'weather_after_start','weather_time_parse_failed','airport_code','weather_condition','wind_direction']
env_cols += [b for _, b, g in mapping if g in ['附近设施标记','昼夜类别']]
for c in numeric_rules:
    if c != 'distance_mi':
        env_cols += [c,c+'_raw',c+'_invalid',c+'_missing']
env_cols += [c+'_missing' for _,c,g in mapping if g=='附近设施标记']
env_cols += ['weather_condition_missing','weather_time_local_missing']
export_query('SELECT '+','.join(env_cols)+' FROM la', RUN / '02_los_angeles/environment.parquet')
con.execute('''CREATE VIEW text_events AS SELECT event_id, start_time_local, end_time_local,
 week_start_local, description, description_missing, description_asof_status,
 end_before_start, end_relative_to_start_week,
 CASE WHEN description IS NOT NULL THEN sha256(description) END AS text_key FROM la''')
export_query('SELECT * FROM text_events', RUN / '03_text/los_angeles_text_events.parquet')
export_query('SELECT * FROM text_events WHERE description IS NOT NULL',
             RUN / '03_text/los_angeles_text_candidates.parquet')
export_query('''SELECT text_key,description,count(*) event_count FROM text_events
 WHERE description IS NOT NULL GROUP BY 1,2''', RUN / '03_text/unique_texts.parquet')
print('主表、环境表、文本表与隔离表已写出。')
""")
md('''
## 5 质量清单与覆盖描述

输出全国各年、各州及城市每周的记录量，用于后续发现缺口。出现记录的周才会在城市周计数表中列出，缺失行不能直接解释为零事故。记录量变化也不能自动证明采集断档。

同坐标、同时间、不同 ID 的组只列入复核表，避免删除同一地点真实的不同事件。数值分位数用于提示极端值，不据此裁剪数据。
''')
code(r"""
qa = RUN / '04_quality'
con.execute('SELECT state,event_year,count(*) records FROM clean GROUP BY 1,2 ORDER BY 1,2').df().to_csv(
    qa / 'state_year_counts.csv',index=False,encoding='utf-8-sig')
export_query('''SELECT state,city,week_start_local,count(*) records FROM clean
 GROUP BY 1,2,3''', qa / 'observed_city_week_counts.parquet')
export_query('''SELECT start_time_local,start_lat,start_lng,count(*) record_count
 FROM clean GROUP BY 1,2,3 HAVING count(*)>1''', qa / 'same_time_location_groups.parquet')
flag_names = [r[0] for r in con.execute('DESCRIBE clean').fetchall()
              if r[0].endswith(('_missing','_invalid','_parse_failed')) or r[0]=='end_before_start']
flag_values = con.execute('SELECT '+','.join(f'count(*) FILTER (WHERE {c})' for c in flag_names)+' FROM clean').fetchone()
quality_flags = pd.DataFrame({'flag':flag_names,'rows':flag_values})
quality_flags.to_csv(qa / 'quality_flag_counts.csv',index=False,encoding='utf-8-sig')
stats = []
for col in numeric_rules:
    row = con.execute(f'''SELECT count({col}),min({col}),quantile_cont({col},0.5),
      quantile_cont({col},0.99),max({col}) FROM clean''').fetchone()
    stats.append([col,*row])
pd.DataFrame(stats,columns=['field','nonmissing','min','median','p99','max']).to_csv(
    qa / 'numeric_summary.csv',index=False,encoding='utf-8-sig')
print('缺失及无效字段统计（前十行）')
display(quality_flags.sort_values('rows',ascending=False).head(10))
""")
md('''
## 6 验收与发布

验收从已经写到磁盘的文件重新读取，检查全国行数、事件 ID 唯一性、起点和时间可用性、洛杉矶各表行数与 ID 一致、文本候选及复用映射一致。校验通过才写 COMPLETE 标记并更新最新运行入口。
''')
code(r"""
national_pattern = (RUN / '01_national/events/**/*.parquet').as_posix()
con.execute(f'CREATE VIEW saved AS SELECT * FROM read_parquet({sql_string(national_pattern)},hive_partitioning=false)')
kept = int(counts.iloc[0]['kept'])
la_count = int(counts.iloc[0]['la'])
saved_stats = con.execute('''SELECT count(*),count(DISTINCT event_id),
 count(*) FILTER (WHERE start_time_local IS NULL OR start_lat IS NULL OR start_lng IS NULL) FROM saved''').fetchone()
assert saved_stats == (kept,kept,0), saved_stats
assert kept + int(audit.loc[audit.disposition!='kept','rows'].sum()) == raw_count
for name, path in [('saved_core','02_los_angeles/events_core.parquet'),
                   ('saved_env','02_los_angeles/environment.parquet'),
                   ('saved_text','03_text/los_angeles_text_events.parquet')]:
    con.execute(f'CREATE VIEW {name} AS SELECT * FROM read_parquet({sql_string((RUN/path).as_posix())})')
    assert con.execute(f'SELECT count(*),count(DISTINCT event_id) FROM {name}').fetchone()==(la_count,la_count)
    assert con.execute(f'''SELECT count(*) FROM (SELECT event_id FROM la EXCEPT
                          SELECT event_id FROM {name})''').fetchone()[0]==0
candidate_path = sql_string((RUN/'03_text/los_angeles_text_candidates.parquet').as_posix())
unique_path = sql_string((RUN/'03_text/unique_texts.parquet').as_posix())
text_count = con.execute('SELECT count(*) FROM saved_text WHERE description IS NOT NULL').fetchone()[0]
assert con.execute(f'SELECT count(*) FROM read_parquet({candidate_path})').fetchone()[0] == text_count
assert con.execute(f'SELECT coalesce(sum(event_count),0) FROM read_parquet({unique_path})').fetchone()[0] == text_count
assert con.execute(f'''SELECT count(*) FROM read_parquet({candidate_path}) c LEFT JOIN
 read_parquet({unique_path}) u USING(text_key) WHERE u.text_key IS NULL OR c.description<>u.description''').fetchone()[0]==0
output_inventory = []
for path in sorted(RUN.rglob('*.parquet')):
    if '_work' in path.parts:
        continue
    f = pq.ParquetFile(path)
    output_inventory.append({'path':path.relative_to(RUN).as_posix(),'rows':f.metadata.num_rows,
                             'columns':len(f.schema_arrow),'bytes':path.stat().st_size})
pd.DataFrame(output_inventory).to_csv(RUN/'05_metadata/output_inventory.csv',index=False,encoding='utf-8-sig')
clean_schema = pd.DataFrame(con.execute('DESCRIBE saved').fetchall(),
                           columns=['column_name','column_type','null','key','default','extra'])
clean_schema[['column_name','column_type']].to_csv(RUN/'05_metadata/clean_schema.csv',index=False,encoding='utf-8-sig')
metadata = {'run_id':run_id,'python':sys.executable,'raw_rows':raw_count,'kept_rows':kept,
 'los_angeles_rows':la_count,'text_candidates':text_count,'local_timestamp_min':str(counts.iloc[0]['first_start']),
 'local_timestamp_max':str(counts.iloc[0]['last_start']),
 'city_selection':"State='CA' AND lower(trim(City))='los angeles'; source labels, not municipal polygon",
 'scope':'cleaning only; no grid, train split, prediction or text inference',
 'packages':{p:importlib.metadata.version(p) for p in ['pandas','pyarrow','duckdb','nbformat','nbclient','ipykernel']},
 'validation':'all assertions passed'}
(RUN/'05_metadata/run_manifest.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
report = f'''# 美国交通事故清洗数据

本次运行 {run_id} 已完成并通过磁盘回读校验。全国原始记录 {raw_count:,} 条，主表保留 {kept:,} 条，洛杉矶城市标签记录 {la_count:,} 条，其中非空文本 {text_count:,} 条。

## 文件用途

| 位置 | 内容与用途 |
| --- | --- |
| 01_national/events | 按州分区的全国主表。需要其他城市或正式边界时可重新裁剪。 |
| 02_los_angeles/events_core.parquet | 洛杉矶事件基础信息，供后续投影、网格和周计数。 |
| 02_los_angeles/environment.parquet | 与基础表一对一的环境特征，按 event_id 连接。 |
| 03_text/los_angeles_text_events.parquet | 同一批事件的历史描述，保留缺失文本及时间质量标记。 |
| 03_text/los_angeles_text_candidates.parquet | 非空描述候选，需要另行核查预测时是否可得。 |
| 03_text/unique_texts.parquet | 完全相同文本的复用键，方便后续缓存提取结果。 |
| 04_quality | 行去留、隔离记录、缺失统计、重复时间地点组、数值分位数及城市周覆盖。 |
| 05_metadata | 原始文件哈希、字段映射、清洗表 schema、输出清单和环境版本。 |

## 使用规则

1. 所有事件表用 event_id 连接，先确认一对一。天气或描述缺失仍保留基础事件。
2. 时间是当地时间；timezone 独立保留。源数据版本及文本发布时间尚不能证明实时可得性。description_asof_status 全部为 unverified。
3. 洛杉矶依据原表城市名称筛选；真正的行政边界及边缘邻格需要后续 GIS 定义。全国主表可补充边界附近事件。
4. 可选数值仅清除违反定义的值，原值在 *_raw 列，空值仍为空。气温负数保留。其他极端值可参考质量清单，并在训练期确定处理方式。
5. 阴性网格周、训练验证测试划分、归一化、独热编码、文本推理与预测均由后续实验建立。
6. 不同 ID 的同时间同地点记录没有自动删除。冲突 ID 和硬性不可用的事件放在隔离表；删除副本的数量与来源另行登记。
7. observed_city_week_counts 仅含有记录的城市周。缺少一行不能证明该城市当周为零事故。
8. 当前原始记录从 2016 年 1 月 14 日至 2023 年 3 月 31 日，首尾观测周并非完整周，各城市还需单独检查起止日期；当前清洗保留这些真实记录，后续构造完整周样本时再处理。

清洗规则及执行结果见 [02 notebook](../../notebooks/02_us_accidents_cleaning.ipynb)。
'''
(RUN/'README.md').write_text(report,encoding='utf-8')
con.close()
# 仅删除本次运行生成的明确数据库文件，原始数据和清洗产物均保留。
for suffix in ['cleaning.duckdb','cleaning.duckdb.wal']:
    path = RUN / '_work' / suffix
    if path.is_file():
        path.unlink()
(RUN/'COMPLETE').write_text('All validation checks passed.',encoding='utf-8')
(RUN/'RUNNING').unlink()
pointer = root/'LATEST_RUN.tmp'
pointer.write_text(run_id,encoding='utf-8')
pointer.replace(root/'LATEST_RUN.txt')
(root/'README.md').write_text(f'# 清洗数据入口\n\n最新完成的运行见 [{run_id}]({run_id}/README.md)。\n\n每次完整运行 notebook 会创建新目录，旧运行可继续复查。只使用带 COMPLETE 标记的目录。\n',encoding='utf-8')
print('全部验收通过，已发布', RUN)
display(pd.DataFrame(output_inventory).head(8))
""")

nb = nbf.v4.new_notebook(cells=cells)
nb.metadata['kernelspec'] = {'display_name':'Python (7308-Final-project)', 'language':'python','name':'7308-final-project'}
nb.metadata['language_info'] = {'name':'python','version':'3.11.18'}
dest = PROJECT / 'notebooks/02_us_accidents_cleaning.ipynb'
nbf.validate(nb)
nbf.write(nb, dest)
print(dest)
