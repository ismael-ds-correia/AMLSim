package amlsim.model.cash;

import java.util.Random;

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
            return sampleMultiModal(SUSPICIOUS_MIN, SUSPICIOUS_MAX, rand);
        }else{
            return sampleMultiModal(NORMAL_MIN, NORMAL_MAX, rand);
        }
    }

    private float sampleMultiModal(float min, float max, Random rand) {
        double modeSelector = rand.nextDouble();
        
        if (modeSelector < 0.12) {
            // Modo 1: Valores pequenos (log₁₀ ≈ 0.6, R$4)
            double mu = 1.39;
            double sigma = 1.3;  // Aumentar de 0.9 para 1.3 (mais dispersão)
            double value = Math.exp(mu + sigma * rand.nextGaussian());
            return Math.max(min, Math.min(max, (float)value));
        } else if (modeSelector < 0.55) {
            // Modo 2: Pico principal (log₁₀ ≈ 2.5, R$316)
            double mu = 5.76;
            double sigma = 1.0;
            double value = Math.exp(mu + sigma * rand.nextGaussian());
            return Math.max(min, Math.min(max, (float)value));
        } else {
            // Modo 3: Cauda (log₁₀ ≈ 3.5, R$3162)
            double mu = 8.06;
            double sigma = 1.2;
            double value = Math.exp(mu + sigma * rand.nextGaussian());
            return Math.max(min, Math.min(max, (float)value));
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
            int maxTx = 200;
            double alpha = 0.8;
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
