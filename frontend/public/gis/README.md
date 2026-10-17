# 漕河泾科技绿洲公开 GIS 基础数据

`caohejing-keji-oasis.geojson` 由同目录的 OpenStreetMap XML 提取生成。范围对应上海市闵行区虹桥镇的漕河泾科技绿洲公开地图关系 `16531277`，坐标系为 WGS 84（EPSG:4326）。

- 来源：OpenStreetMap contributors
- 许可：[ODbL 1.0](https://www.openstreetmap.org/copyright)
- 获取日期：2026-10-10
- 包含：公开地图中的建筑、道路、水体、绿地、公共设施和入口。

重新生成：`python3 scripts/import-caohejing-osm.py`。

## 参数化建筑模型

GIS 页保留公开建筑轮廓。带有 OpenStreetMap 高度或楼层属性的建筑直接采用该属性；没有公开高度的建筑，按园区常见 5–13 层研发办公建筑范围生成体量，并由浏览器生成窗格、层间线和屋顶轮廓。该外立面是为演示数字孪生空间关系生成的程序化模型，不是实景摄影、航空测绘、BIM 或竣工资料。点击建筑可查看本次模型的属性来源与近似说明。

项目中的设备、地下管网、内涝、泄漏和应急推演对象是演示仿真资产，只以“关联到园区 GIS 坐标”的方式显示；它们不是公开或测绘的真实园区地下基础设施数据。
