import { use } from 'echarts/core';
import { BarChart, GraphChart, LineChart, PieChart } from 'echarts/charts';
import {
  DatasetComponent,
  GridComponent,
  LegendComponent,
  ToolboxComponent,
  TitleComponent,
  TooltipComponent
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

use([
  BarChart,
  CanvasRenderer,
  DatasetComponent,
  GraphChart,
  GridComponent,
  LegendComponent,
  LineChart,
  PieChart,
  ToolboxComponent,
  TitleComponent,
  TooltipComponent
]);
