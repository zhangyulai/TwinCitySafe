import {api} from './client';import {validPrediction,type RiskPrediction,type RiskModelStatus,type PredictionExplanation,type PredictionEvaluation} from '../types/risk';
export const riskApi={
 async prediction(signal?:AbortSignal):Promise<RiskPrediction>{const {data}=await api.get<unknown>('/risk/prediction',{signal});if(!validPrediction(data))throw new Error('预测返回格式无效');return data;},
 async status(signal?:AbortSignal){return (await api.get<RiskModelStatus>('/risk/model/status',{signal})).data;},
 async explanation(signal?:AbortSignal){return (await api.get<PredictionExplanation>('/risk/prediction/explanation?minutes=30',{signal})).data;},
 async evaluation(signal?:AbortSignal){return (await api.get<PredictionEvaluation>('/risk/evaluation',{signal})).data;},
};
