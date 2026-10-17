from app.schemas.operation import Advice

class MaintenanceAdviceService:
    @staticmethod
    def build(health, level, contributions, fault):
        if level == "unavailable":
            return "异常模型未加载，仍显示规则健康指数。", Advice(priority="P3", title="恢复诊断模型", message="请加载仿真训练模型；当前不能据此判断多变量异常。")
        if level in ("not_applicable", "warming_up"):
            return "设备待机、离线或启动过渡中，运行工况异常模型暂不评估。", Advice(priority="P3", title="计划维护", message="建议确认设备状态，按计划检查备用泵；进入稳定运行后再评估。")
        names = [item.label for item in contributions if item.contribution > 0][:2]
        reason = "与正常基线相比，" + "、".join(names) + "偏离较明显。" if names else "当前参数接近正常运行基线。"
        reason += "贡献比例来自偏离度分析，不代表模型因果归因。"
        if level == "critical" or health < 30:
            advice = Advice(priority="P0", title="建议立即检查", message="建议停止设备并确认备用泵可用，检查轴承、电机及泵体固定；此为仿真诊断建议，不自动执行停机。")
        elif health < 60:
            advice = Advice(priority="P1", title="建议 2 小时内检查", message="建议关注持续健康下降，安排轴承磨损、润滑及电机负载检查。")
        elif level == "warning":
            advice = Advice(priority="P2", title="建议 24 小时内检查", message="建议检查轴承磨损、底座紧固和润滑状态，并复核电流及效率变化。")
        elif level == "attention":
            advice = Advice(priority="P3", title="持续观察", message="参数出现偏离趋势，建议增加观察并核对工况，避免仅凭单次读数判断损坏。")
        else:
            advice = Advice(priority="P3", title="计划维护", message="设备运行参数接近正常基线，建议按计划维护。")
        if fault != "normal":
            reason += " 当前启用了开发故障工况；建议仅供软件演示。"
        return reason, advice
