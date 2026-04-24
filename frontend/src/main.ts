import { createPinia } from 'pinia';
import { createApp } from 'vue';
import { Splitpanes, Pane } from 'splitpanes';
import 'splitpanes/dist/splitpanes.css';
import { OhVueIcon, addIcons } from 'oh-vue-icons';
import {
  MdAdd, MdStorage, MdDeleteoutline, MdPlayarrow, MdStop,
  MdChevronright, MdChevronleft, MdUpload, MdSave, MdClose,
  MdSettings, MdPerson, MdDashboard, MdBarchart, MdCode,
  MdContentcopy, MdArrowforward, MdAccesstime, MdTablechart,
  MdTablerows, MdFilterlist, MdStar, MdWarning, MdSwapvert,
  MdDescription, MdChatbubbleoutline,
} from 'oh-vue-icons/icons/md';
import App from './App.vue';
import router from './router';
import './plugins/echarts';
import './assets/styles.scss';

addIcons(
  MdAdd, MdStorage, MdDeleteoutline, MdPlayarrow, MdStop,
  MdChevronright, MdChevronleft, MdUpload, MdSave, MdClose,
  MdSettings, MdPerson, MdDashboard, MdBarchart, MdCode,
  MdContentcopy, MdArrowforward, MdAccesstime, MdTablechart,
  MdTablerows, MdFilterlist, MdStar, MdWarning, MdSwapvert,
  MdDescription, MdChatbubbleoutline,
);

const app = createApp(App);

app.use(createPinia());
app.use(router);
app.component('Splitpanes', Splitpanes);
app.component('Pane', Pane);
app.component('v-icon', OhVueIcon);
app.mount('#app');
