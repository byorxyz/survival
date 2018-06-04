import abc
import numpy as np
import matplotlib.pyplot as plt
import scipy.integrate as integrate
from misc.misc import *


class Base(object):
    '''
    Numerically integrates the PDF and obtains the 
    expected value of x conditional on x less than y.
    '''
    __metaclass__ = abc.ABCMeta

    def expctd_x_given_x_le_y(self,xs = np.arange(1,100000)*0.01):
        vals = []
        # \int_0^t x f_x dx
        for i in xs:
            vals.append((i+0.005)*self.pdf(i+0.005)*0.01)
        return np.cumsum(vals)

    def expctd_x_bw_lts(self, t1, t2, k=None, lmb=None):
        ress = integrate.quad(lambda x: x * self.pdf(x,k,lmb), t1, t2)
        prob = self.cdf(t2,k,lmb) - (self.cdf(t1,k,lmb) if t1 > 0 else 0)
        return ress[0]/prob
    
    def expctd_downtime(self,y,xs=np.arange(1,100000)*0.01,lmb=0,reg='log'):
        '''
        Combines the expected downtime when the recovery happens before 
        and after the wait threshold.
        '''
        highterms = self.survival(xs)*(xs+y)
        lowterms = self.Ex_x_le_y(xs)
        et = lowterms + highterms
        if reg == 'log':
            et += lmb*np.log(xs)
        elif reg == 'sqrt':
            et += lmb*xs**.5
        elif reg == 'sqr':
            et += lmb*xs**2
        return et

    def hazard(self, t):
        return self.pdf(t)/self.survival(t)

    def determine_params(self, k=-1, lmb=-1, params=None):
        if params is not None:
            k = params[0]
            lmb = params[1]
        else:
            if k is None or k < 0:
                k = self.k
            if lmb is None or lmb < 0:
                lmb = self.lmb
        return [k,lmb]

    def prob_t_gr_tau(self,xs=np.arange(1,100000)*0.01,lmb=0.2,t0=900.0,Y=480.0):
        '''
        The probability that the current distribution is greater than t0.
        '''
        return lmb*((xs>t0)*(self.survival(t0)-self.survival(xs)) + (xs> (t0-Y))*self.survival(xs))

    def expected_t(self,tau,k=None,lmb=None,params = None):
        [k,lmb] = self.determine_params(k,lmb,params)
        return self.expectedXBwLts(0,tau,k,lmb)

    def plt_downtime(self,xs=np.arange(1,100000)*0.01,lmb=0,alp=1,lmb_prob=0,t0=900.0,Y=480.0,reg='log',col='b'):
        ys = self.expected_downtime(480.0,xs=xs,lmb=lmb,reg=reg)
        ys_probs = self.prob_TgrTau(xs,lmb_prob,t0,Y)
        plt.plot(xs,(ys+ys_probs),alpha=alp,color=col)
        return (ys+ys_probs)

    def optimal_wait_threshold(self, intervention_cost):
        return solve_hazard_eqn(self.hazard, 1/intervention_cost)

    def set_params(self, k, lmb, params):
        if params is not None:
            [k, lmb] = params[:2]
        self.k = k
        self.lmb = lmb
        self.params = [k, lmb]


    def gradient_descent(self, numIter=2001, params = np.array([2.0,2.0]), verbose=False, gamma=0, params0=np.array([167.0, 0.3]),
        step_lengths=[1e-8,1e-7,1e-5,1e-3,1e-2,.1, 10, 50, 70, 120, 150, 200, 250, 270, 300, 500, 1e3, 1.5e3, 2e3, 3e3]):
        for i in range(numIter):
            #lik = self.loglik(self.train_org,self.train_inorg,params[0],params[1],params[2])
            directn = self.grad(self.train_org, self.train_inorg, params[0],params[1])#-2*gamma*sum((params-params0))
            if i%100 > 80:
                directn[np.random.choice(len(params),1)[0]] = 0 # Randomly set one coordinate to zero.
            params2 = params + 1e-10*directn
            lik = self.loglik(self.train_org, self.train_inorg, params2[0], params2[1])#+gamma*sum((params2-params0)**2)
            alp_used = step_lengths[0]
            for alp1 in step_lengths:
                params1 = params + alp1 * directn
                if(min(params1) > 0):
                    lik1 = self.loglik(self.train_org,self.train_inorg,params1[0],params1[1])#+gamma*sum((params1-params0)**2)
                    if(lik1 > lik and np.isfinite(lik1)):
                        lik = lik1
                        params2 = params1
                        alp_used = alp1
            params = params2
            if i%100 == 0:
                if verbose:
                    print("Itrn " + str(i) + " ,obj fn: " + str(lik) + " \nparams = " + str(params) + " \ngradient = " + str(directn) + "\nstep_len="+str(alp_used))
                    print("\n########\n")
        self.set_params(params[0], params[1], params)
        self.final_loglik = lik
        return params


    def newtonRh(self, numIter=101, params = np.array([1.0,0.5]), verbose=False):
        '''
        Fits the parameters of a distribution to data (censored and uncensored).
        Uses the Newton Raphson method for explanation, see: https://www.youtube.com/watch?v=acsSIyDugP0
        args:
            numIter: The maximum number of iterations for the iterative method
            params: The initial guess for the shape and scale parameters respectively.
            verbose: Set to true for debugging. Shows progress as it fits data.
        '''
        for i in range(numIter):
            directn = self.grad(self.train_org,self.train_inorg,params[0],params[1])
            #if sum(abs(directn)) < 1e-5:
            #    if verbose:
            #        print("\nIt took: " + str(i) + " Iterations.\n Gradients - " + str(directn))
            #    self.set_params(params[0], params[1], params)
            #    self.final_loglik = lik
            #    return params
            lik = self.loglik(self.train_org,self.train_inorg,params[0],params[1])
            step = np.linalg.solve(self.hessian(self.train_org,self.train_inorg,params[0],params[1]),directn)
            params = params - step
            if min(params) < 0:
                print("Drastic measures")
                params = params + step # undo the effect of taking the step.
                params2 = params
                for alp1 in [1e-8,1e-7,1e-5,1e-3,1e-2,.1,.2,.3,.4,.5,.6,.7,.8,.9,1.0]:
                    params1 = params - alp1 * step
                    if(max(params1) > 0):
                        lik1 = self.loglik(self.train_org,self.train_inorg,params1[0],params1[1])
                        if(lik1 > lik and np.isfinite(lik1)):
                            lik = lik1
                            params2 = params1
                            scale = alp1
                params = params2
            if i % 10 == 0 and verbose:
                print("Iteration " + str(i) + " ,objective function: " + str(lik) + " \nparams = " + str(params) + " \nGradient = " + str(directn) + "\n##\n\n")
        self.set_params(params[0], params[1], params)
        self.final_loglik = lik
        return params


    def construct_matrices(self, tau, intervention_cost=200):
        x = 0
        pless = self.cdf(tau) - self.cdf(x)
        pmore = self.survival(tau)
        tless = self.expctd_x_bw_lts(x,tau)
        t0 = np.array([0, tau, tless])
        p0 = np.array([0, pmore/(pmore+pless), pless/(pmore+pless)])
        probs = np.array(
        [
          p0,
          [0,0,1],
          [0.1,0.9,0]
        ])
        times = np.array(
        [
          t0,
          [0,0,intervention_cost],
          [100,100,0]
        ])
        return (np.matrix(probs), np.matrix(times))

