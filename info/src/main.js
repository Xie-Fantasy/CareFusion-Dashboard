import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import './assets/styles/global.scss'
import * as echarts from 'echarts'
import DataVVue3 from '@kjgl77/datav-vue3'

window.echarts = echarts

const app = createApp(App)
app.use(DataVVue3)
app.mount('#app')