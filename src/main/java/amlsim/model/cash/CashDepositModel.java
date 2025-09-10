package amlsim.model.cash;

import amlsim.Account;
import amlsim.Branch;

/**
 * Cash-in (deposit) model via cash (CNAB 220)
 */
public class CashDepositModel extends CashModel {

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
        System.out.println("CashDepositModel params: Norm: " + NORMAL_INTERVAL + " Case: " + SUSPICIOUS_INTERVAL);
    }

    private boolean isNextStep(long step){
        // Implemente sua lógica de agendamento aqui, se necessário
        return true;
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
        return "CASH-DEPOSIT";
    }

    @Override
    public void makeTransaction(long step) {
        if(isNextStep(step)){
            Branch branch = account.getBranch();
            float amount = computeAmount();
            makeTransaction(step, amount, account, branch, "CASH-DEPOSIT");
        }
    }

    protected void makeTransaction(long step, Account orig, Account bene, double amount, String desc) {
        boolean isSAR = bene.isSAR();
        long alertID = 0L;
        amlsim.AMLSim.handleTransaction(step, desc, amount, orig, bene, isSAR, alertID);
    }

    public void registerCashDeposit(long step, double amount, String description) {
        this.makeTransaction(step, this.account.getBranch(), this.account, amount, description);
    }
}