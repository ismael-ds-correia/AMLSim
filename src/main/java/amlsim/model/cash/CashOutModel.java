package amlsim.model.cash;

import amlsim.AMLSim;
import amlsim.Branch;

/**
 * Cash-out (withdrawal) model
 */
public class CashOutModel extends CashModel {

    private static int NORMAL_INTERVAL = 1;
    private static int SUSPICIOUS_INTERVAL = 1;
    private static float NORMAL_MIN = 10;
    private static float NORMAL_MAX = 100;
    private static float SUSPICIOUS_MIN = 10;
    private static float SUSPICIOUS_MAX = 100;

    public static void setParam(int norm_int, int case_int, float norm_min, float norm_max, float case_min, float case_max){
        NORMAL_INTERVAL = norm_int;
        SUSPICIOUS_INTERVAL = case_int;
        NORMAL_MIN = norm_min;
        NORMAL_MAX = norm_max;
        SUSPICIOUS_MIN = case_min;
        SUSPICIOUS_MAX = case_max;
    }

    private boolean isNextStep(long step){
        if(this.account.isSAR()){
            return step % SUSPICIOUS_INTERVAL == 0;
        }else{
            return step % NORMAL_INTERVAL == 0;
        }
    }

    private float computeAmount(){
        if(this.account.isSAR()){
            return SUSPICIOUS_MIN + rand.nextFloat() * (SUSPICIOUS_MAX - SUSPICIOUS_MIN);
        }else{
            return NORMAL_MIN + rand.nextFloat() * (NORMAL_MAX - NORMAL_MIN);
        }
    }

    @Override
    public String getModelName() {
        return "CASH-OUT";
    }

    @Override
    public void makeTransaction(long step) {
        if(isNextStep(step)){
            Branch branch = account.getBranch();
            int minTx = 1;
            int maxTx = 500;
            double alpha = 2.5;
            int eachCount = samplePowerLaw(minTx, maxTx, alpha, rand);

            for(int i = 0; i < eachCount; i++) {
                float amount = computeAmount();
                makeTransaction(step, amount, branch, account, "CASH-OUT");
            }
        }
    }

    public void registerExternalWithdrawal(long step, double amount, String description) {
        // Origem: conta, Destino: agência (branch)
        boolean isSAR = this.account.isSAR();
        long alertID = 0L;
        AMLSim.handleTransaction(step, description, amount, this.account, this.account.getBranch(), isSAR, alertID);
    }

    public void registerExternalWithdrawal(long step, double amount, String description, long alertID) {
        boolean isSAR = this.account.isSAR();
        AMLSim.handleTransaction(step, description, amount, this.account, this.account.getBranch(), isSAR, alertID);
    }
}
