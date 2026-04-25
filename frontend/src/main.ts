import { createApp } from 'vue';
import { Splitpanes, Pane } from 'splitpanes';
import 'splitpanes/dist/splitpanes.css';
import App from './App.vue';
import router from './router';
import { pinia } from './stores/pinia';
import './plugins/echarts';
import './assets/styles.scss';

const app = createApp(App);

app.use(pinia);
app.use(router);
app.component('Splitpanes', Splitpanes);
app.component('Pane', Pane);
app.mount('#app');
